"""FastAPI backend for MemoryMesh."""

from __future__ import annotations
import logging
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import settings
from src.db.connection import check_connection, close_connection
from src.db.schema import bootstrap_schema
from src.services.model_service import check_ollama_health
from src.api.routes import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: bootstrap on startup, cleanup on shutdown."""
    logger.info("MemoryMesh starting up...")

    # Enforce production security guarantees at startup
    settings.validate_production_config()

    # Check FalkorDB
    db_ok = check_connection()
    if db_ok:
        logger.info("✅ FalkorDB connected")
        for tenant in settings.ALLOWED_TENANTS:
            try:
                bootstrap_schema(tenant)
                logger.info(f"  Schema ready for tenant: {tenant}")
            except Exception as e:
                logger.warning(f"  Schema bootstrap failed for {tenant}: {e}")
    else:
        logger.warning("⚠️  FalkorDB not available. Start it with: docker run -p 6379:6379 falkordb/falkordb")

    # Check Ollama
    ollama_health = check_ollama_health()
    if ollama_health["available"]:
        if ollama_health["model_loaded"]:
            logger.info(f"✅ Ollama ready with model: {ollama_health['model']}")
        else:
            logger.warning(f"⚠️  Ollama running but model not found. {ollama_health['error']}")
    else:
        logger.warning(f"⚠️  {ollama_health['error']}")

    yield

    logger.info("MemoryMesh shutting down...")
    close_connection()


app = FastAPI(
    title="MemoryMesh",
    description="AI Project Coordination with Persistent Graph Memory",
    version="1.0.0",
    lifespan=lifespan,
)

from fastapi import Request
from fastapi.responses import JSONResponse

# CORS for Streamlit frontend and configured origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Prevent unhandled exceptions from exposing stack traces or database details."""
    logger.error(
        f"Unhandled exception on {request.method} {request.url.path}: {exc}",
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An internal server error occurred.",
            "path": request.url.path,
        },
    )


app.include_router(router)
