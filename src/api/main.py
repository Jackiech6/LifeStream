"""FastAPI application main entry point."""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config.settings import Settings
from src.api.routes import upload, presigned_upload, status, summary, query

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown."""
    # Startup
    logger.info("Starting LifeStream API...")
    settings = Settings()
    logger.info(f"API configured with region: {settings.aws_region}")
    yield
    # Shutdown
    logger.info("Shutting down LifeStream API...")


# Create FastAPI app
app = FastAPI(
    title="LifeStream API",
    description="REST API for video processing and memory querying",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include routers
app.include_router(upload.router, prefix="/api/v1/upload", tags=["upload"])
app.include_router(presigned_upload.router, prefix="/api/v1/upload", tags=["upload"])
app.include_router(status.router, prefix="/api/v1", tags=["status"])
app.include_router(summary.router, prefix="/api/v1", tags=["summary"])
app.include_router(query.router, prefix="/api/v1", tags=["query"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "LifeStream API",
        "version": "1.0.0",
        "status": "operational",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)},
    )


__all__ = ["app"]
