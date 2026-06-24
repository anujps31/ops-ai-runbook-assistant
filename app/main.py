# Main FastAPI application entry point
# This file initializes and configures the FastAPI application

from fastapi import FastAPI
from app.routes import health
from app.routes import debug
from app.routes import rag
from app.routes import incident

# Import application settings and logger utilities
# - `settings` centralizes environment-driven configuration
# - `get_logger` provides a configured logger that respects LOG_LEVEL
from app.utils.config import settings
from app.utils.logger import get_logger
from app.utils.exceptions import init_exception_handlers



# Create a module-level logger for this module. Using __name__ helps
# identify the source module in logs (useful in multi-module applications).
logger = get_logger(__name__)


# Create the FastAPI application instance using values from `settings`.
# Using settings here keeps metadata synchronized with environment/config.
app = FastAPI(
    title=settings.APP_NAME,                              # Display name in API docs
    description="AI-powered incident response automation platform",
    version=settings.APP_VERSION,                         # Use configured app version
)


# Register the health routes with the main application
# This makes all routes from the health router available (e.g., /health)
app.include_router(health.router)
app.include_router(debug.router)
app.include_router(rag.router)
app.include_router(incident.router)

init_exception_handlers(app)

# Optional: Root endpoint for basic API information
@app.get("/")
async def root():
    """
    Root endpoint

    Returns basic information about the API. Keep this lightweight so
    health checks or automated tools can quickly probe the service.
    """
    return {
        "message": "Welcome to OPS AI Runbook Assistant",
        "docs": "/docs",
    }


from app.services.llm_service import LLMService
from app.services.chroma_service import ChromaService


@app.on_event("startup")
async def on_startup() -> None:
    logger.info("Starting application: %s", settings.APP_NAME)
    logger.info("Version: %s", settings.APP_VERSION)
    logger.info("Ollama base URL: %s", settings.OLLAMA_BASE_URL)

    ollama = LLMService()
    if ollama.verify_connection():
        logger.info("Ollama verification succeeded")
    else:
        logger.error("Ollama verification failed on startup")

    try:
        chroma = ChromaService()
        logger.info("ChromaDB verification succeeded, document count=%s", chroma.count())
    except Exception as ex:
        logger.exception("ChromaDB verification failed: %s", ex)


@app.get("/health")
async def health_check():
    logger.info("/health endpoint called")
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


@app.get("/metrics")
async def metrics():
    logger.info("/metrics endpoint called")
    return {
        "status": "ok",
        "app_version": settings.APP_VERSION,
        "ollama_url": settings.OLLAMA_BASE_URL,
    }


# Entry point for running the application directly (development convenience)
if __name__ == "__main__":
    import uvicorn

    host = getattr(settings, "HOST", "0.0.0.0")
    port = getattr(settings, "PORT", 8000)

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=True,
    )
