from datetime import datetime
from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, Form, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from pathlib import Path
import base64
import logging
import json
import os
from motor.motor_asyncio import AsyncIOMotorClient
from bson.binary import Binary
from vuforia_client.cloud_target_webapi_client import VuforiaVwsClient, CloudTargetWebAPIClient, CloudQueryWebAPIClient
from dotenv import load_dotenv
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend
from fastapi_cache.decorator import cache

app = FastAPI()
router = APIRouter()
logger = logging.getLogger(__name__)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load environment variables
load_dotenv()
server_access_key = os.getenv("VWS_SERVER_ACCESS_KEY")
server_secret_key = os.getenv("VWS_SERVER_SECRET_KEY")
client_access_key = os.getenv("VWS_CLIENT_ACCESS_KEY")
client_secret_key = os.getenv("VWS_CLIENT_SECRET_KEY")
mongodb_url = os.getenv("MONGODB_URL", "mongodb://localhost:27017")

# MongoDB setup
db_client = AsyncIOMotorClient(mongodb_url)
db = db_client.vuforia_db

class TargetResponse(BaseModel):
    target_id: str
    status: str
    message: str
    details: Optional[Dict[str, Any]] = None

@router.post("/create", response_model=TargetResponse)
async def create_target(
    image: UploadFile,
    name: str = Form(...),
    metadata_base64: str = Form(...),
    width: float = Form(1.0),
    active: bool = Form(True),
    description_en: str = Form(...),
    translations: str = Form(...),
    latitude: float = Form(...),
    longitude: float = Form(...),
):
    """
    Create a new target in Vuforia cloud database with image, name, and metadata.
    """
    try:
        vws_client = VuforiaVwsClient(
            api_base="https://vws.vuforia.com",
            access_key=server_access_key,
            secret_key=server_secret_key
        )
        client = CloudTargetWebAPIClient(vws_client)

        # Create temporary directory if it doesn't exist
        os.makedirs("/tmp", exist_ok=True)

        # Save the uploaded image temporarily
        image_path = Path(f"/tmp/{image.filename}")
        contents = await image.read()
        with open(image_path, "wb") as image_file:
            image_file.write(contents)

        try:
            # Create target in Vuforia
            response = client.create_target(
                image=image_path,
                name=name,
                width=width,
                metadata_base64=metadata_base64,
                active=active
            )
            response_data = response.json()
            await FastAPICache.clear()

            # Store in MongoDB
            mongo_doc = {
                "target_id": response_data["target_id"],
                "name": name,
                "image_data": Binary(contents),
                "metadata_base64": metadata_base64,
                "width": width,
                "active": active,
                "created_at": datetime.utcnow(),
                "description_en": description_en,
                "translations": json.loads(translations),
                "latitude": latitude,
                "longitude": longitude,
                "vuforia_response": response_data
            }
            
            await db.targets.insert_one(mongo_doc)



            # Clean up the temporary file
            os.remove(image_path)

            return TargetResponse(
                target_id=response_data["target_id"],
                status="success",
                message="Target created successfully",
                details=response_data
            )

        except Exception as e:
            if image_path.exists():
                os.remove(image_path)
            raise e

    except Exception as e:
        logger.error(f"Error creating target: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/list_targets", response_model=List[Dict[str, Any]])
@cache(expire=120)
async def list_targets():
    """
    List all target IDs and their details from the Vuforia cloud database.
    """
    try:
        # Initialize Vuforia client with configuration
        vws_client = VuforiaVwsClient(
            api_base="https://vws.vuforia.com",
            access_key=server_access_key,
            secret_key=server_secret_key
        )
        client = CloudTargetWebAPIClient(vws_client)

        # Get list of target IDs
        list_response = client.list_targets()
        logger.debug(f"List targets response: {list_response.json()}")
        target_ids = list_response.json().get("results", [])

        # Fetch details for each target
        target_details = []
        for target_id in target_ids:
            try:
                target_response = client.get_target(target_id)
                target_data = target_response.json()
                target_details.append(target_data)
            except Exception as e:
                logger.error(f"Error fetching details for target {target_id}: {str(e)}")
                target_details.append({"target_id": target_id, "error": str(e)})

        return target_details
    except Exception as e:
        logger.error(f"Error listing targets: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Initialize cache
@app.on_event("startup")
async def on_startup():
    FastAPICache.init(InMemoryBackend(), prefix="fastapi-cache")

@router.get("/target/{target_id}", response_model=TargetResponse)
async def get_target(target_id: str):
    """
    Get target information including metadata from Vuforia cloud database.
    """
    try:
        vws_client = VuforiaVwsClient(
            api_base="https://vws.vuforia.com",
            access_key=server_access_key,
            secret_key=server_secret_key
        )
        client = CloudTargetWebAPIClient(vws_client)

        # Get target info which includes metadata
        response = client.get_target(target_id)
        response_data = response.json()

        # Get the target report which might contain additional info
        report_response = client.get_target_report(target_id)
        report_data = report_response.json()

        # Combine the data
        combined_data = {
            **response_data,
            "target_record": {
                **response_data.get("target_record", {}),
                **report_data.get("target_record", {}),
            }
        }

        # If there's metadata in the response, decode it
        if "application_metadata" in combined_data.get("target_record", {}):
            metadata_base64 = combined_data["target_record"]["application_metadata"]
            try:
                decoded_metadata = base64.b64decode(metadata_base64).decode('utf-8')
                combined_data["target_record"]["metadata_decoded"] = decoded_metadata
            except:
                combined_data["target_record"]["metadata_decoded"] = None

        return TargetResponse(
            target_id=target_id,
            status="success",
            message="Target retrieved successfully",
            details=combined_data
        )
    except Exception as e:
        logger.error(f"Error getting target: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/mongodb/target/{target_id}")
async def get_target_from_mongodb(target_id: str):  
    """
    Get target information from MongoDB.
    """
    try:
        target = await db.targets.find_one({"target_id": target_id})
        if not target:
            raise HTTPException(status_code=404, detail="Target not found in MongoDB")
        
        # Convert ObjectId to string and remove binary image data from response
        target['_id'] = str(target['_id'])
        target.pop('image_data', None)
        
        return target
    except Exception as e:
        logger.error(f"Error getting target from MongoDB: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/mongodb/image/{target_id}")
async def get_target_image(target_id: str):
    """
    Get the image data for a target from MongoDB.
    """
    try:
        target = await db.targets.find_one({"target_id": target_id})
        if not target or 'image_data' not in target:
            raise HTTPException(status_code=404, detail="Image not found")

        return {
            "image_data": base64.b64encode(target['image_data']).decode('utf-8')
        }
    except Exception as e:
        logger.error(f"Error getting image from MongoDB: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/mongodb/targets")
async def list_targets_from_mongodb():
    """
    List all targets from MongoDB.
    """
    try:
        targets = []
        async for target in db.targets.find():
            target['_id'] = str(target['_id'])
            target.pop('image_data', None)
            targets.append(target)
        
        return targets
    except Exception as e:
        logger.error(f"Error listing targets from MongoDB: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Include the router in the app
app.include_router(router, prefix="/api/vuforia", tags=["vuforia"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)