from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any
from pathlib import Path
import base64
import logging
import json
import os
from vuforia_client.cloud_target_webapi_client import VuforiaVwsClient, CloudTargetWebAPIClient, CloudQueryWebAPIClient
from dotenv import load_dotenv
import os
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

# Vuforia credentials

# Load environment variables
load_dotenv()
server_access_key = os.getenv("VWS_SERVER_ACCESS_KEY")
server_secret_key = os.getenv("VWS_SERVER_SECRET_KEY")
client_access_key = os.getenv("VWS_CLIENT_ACCESS_KEY")
client_secret_key = os.getenv("VWS_CLIENT_SECRET_KEY")


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
    active: bool = Form(True)
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
        with open(image_path, "wb") as image_file:
            contents = await image.read()
            image_file.write(contents)

        try:
            # Create target in Vuforia
            response = client.create_target(
                image=image_path,
                name=name,
                width=width,
                metadata_base64=metadata_base64,  # Using application_metadata
                active=active
            )
            response_data = response.json()

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

# Include the router in the app
app.include_router(router, prefix="/api/vuforia", tags=["vuforia"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)