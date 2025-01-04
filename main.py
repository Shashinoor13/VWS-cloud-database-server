from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.main import router

def create_app() -> FastAPI:
    app = FastAPI(
        title="Vuforia API",
        description="API for interacting with the Vuforia cloud database.",
        version="0.1.0"
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router, prefix="/api/v1")

    return app

app = create_app()


