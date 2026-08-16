"""
Main FastAPI application entrypoint for NauDisha Backend API.
Can be executed with:
    uvicorn naudisha.api.main:app --reload
"""

from __future__ import annotations

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from naudisha.api.errors import register_exception_handlers
from naudisha.api.routes import api_router, health_router, ws_router

# Load local .env variables into environment
load_dotenv()


def create_app() -> FastAPI:
    """Factory creating and configuring the NauDisha FastAPI application."""
    application = FastAPI(
        title="NauDisha — Dynamic Ship Routing API",
        description=(
            "REST API backend for NauDisha marine route optimization and vessel tracking. "
            "Integrates multi-factor environmental cost modeling and D* Lite dynamic replanning."
        ),
        version="0.2.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # 1. Enable CORS for frontend clients
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 2. Register standard error handlers (docs/API_CONTRACT.md compliance)
    register_exception_handlers(application)

    # 3. Include Routers
    application.include_router(health_router)
    application.include_router(api_router)
    application.include_router(ws_router)

    return application


app = create_app()
