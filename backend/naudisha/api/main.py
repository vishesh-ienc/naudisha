"""
Main FastAPI application entrypoint for NauDisha Backend API.
Can be executed with:
    uvicorn naudisha.api.main:app --reload
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from dotenv import find_dotenv, load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from naudisha.api.errors import register_exception_handlers
from naudisha.api.routes import api_router, health_router, ws_router
from naudisha.api.tracking import tracking_manager

# Load .env variables from local directory or workspace root
load_dotenv(find_dotenv())


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """
    Runs the navigation simulator for the lifetime of the application.

    A single ticker advances every active tracking session, so vessels keep
    moving whether or not a WebSocket client is attached — which is what lets
    `GET /api/ships/{imo}/status` report genuine movement on its own.
    """
    tracking_manager.start_ticker()
    try:
        yield
    finally:
        await tracking_manager.stop_ticker()


def create_app() -> FastAPI:
    """Factory creating and configuring the NauDisha FastAPI application."""
    application = FastAPI(
        title="NauDisha — Dynamic Ship Routing API",
        description=(
            "REST API backend for NauDisha marine route optimization and vessel tracking. "
            "Integrates multi-factor environmental cost modeling and D* Lite dynamic replanning."
        ),
        version="0.3.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
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
