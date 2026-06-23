# Application configuration module
# Centralizes all environment variables and application settings
# Loads from .env file and environment variables with fallback defaults

from typing import Optional
from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    """
    Application configuration settings
    
    Loads configuration from:
    1. .env file (checked first)
    2. Environment variables (override .env)
    3. Default values (fallback)
    
    This uses Pydantic BaseSettings which handles:
    - Type validation (e.g., PORT must be an integer)
    - Automatic coercion (e.g., "8000" string → 8000 integer)
    - Missing variable detection (raises error if required field missing)
    """
    
    # ============================================================================
    # Application Metadata
    # ============================================================================
    
    APP_NAME: str = "OPS AI Runbook Assistant"
    # Application name used in logging, API docs, and health checks
    # Default: OPS AI Runbook Assistant
    # Load from: APP_NAME environment variable
    
    APP_VERSION: str = "0.1.0"
    # Semantic version string (MAJOR.MINOR.PATCH)
    # Default: 0.1.0
    # Load from: APP_VERSION environment variable
    # Used for: API versioning, monitoring, deployment tracking
    
    # ============================================================================
    # Logging Configuration
    # ============================================================================
    
    LOG_LEVEL: str = "INFO"
    # Python logging level controlling verbosity
    # Default: INFO (production standard)
    # Allowed values: DEBUG, INFO, WARNING, ERROR, CRITICAL
    # Load from: LOG_LEVEL environment variable
    # Purpose: Control log output detail (DEBUG for troubleshooting, INFO for production)
    
    # ============================================================================
    # External Service URLs
    # ============================================================================
    
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    # Base URL for Ollama LLM API endpoint
    # Default: http://localhost:11434 (standard local development)
    # Load from: OLLAMA_BASE_URL environment variable
    # Used for: All LLM inference requests (summarization, analysis, recommendations)
    # Examples:
    #   Local development: http://localhost:11434
    #   Docker service: http://ollama:11434
    #   Production: https://ollama.company.internal
    
    # ============================================================================
    # Server Configuration
    # ============================================================================
    
    HOST: str = "0.0.0.0"
    # Server binding address
    # Default: 0.0.0.0 (listen on all network interfaces)
    # Load from: HOST environment variable
    # Security note: Use 127.0.0.1 to restrict to localhost only
    # Production: Behind reverse proxy, often restricted to internal interface
    
    PORT: int = 8000
    # Server listening port
    # Default: 8000 (standard FastAPI development port)
    # Load from: PORT environment variable
    # Type: Integer (automatically converted from string in .env)
    # Production: Often 80 (HTTP) or 443 (HTTPS) behind reverse proxy
    
    # ============================================================================
    # Pydantic Configuration
    # ============================================================================
    
    class Config:
        """
        Pydantic configuration for the Settings class
        
        Attributes:
            env_file: Path to .env file relative to this module
            env_file_encoding: Character encoding of .env file
            case_sensitive: Whether to match environment variable names with case sensitivity
            extra: Behavior for unexpected configuration variables
        """
        # Look for .env file in project root directory
        env_file: str = str(Path(__file__).parent.parent.parent / ".env")
        # Character encoding for reading .env file
        env_file_encoding: str = "utf-8"
        # Allow both APP_NAME and app_name in .env file (case-insensitive)
        case_sensitive: bool = False
        # Allow undefined variables in .env file without error
        extra: str = "allow"


# Create singleton instance of settings
# This ensures settings are loaded once at application startup
# Use this instance throughout the application instead of creating new Settings()
settings: Settings = Settings()


# ============================================================================
# Usage Examples
# ============================================================================

# In FastAPI routes:
# ─────────────────────────────────────────────────────────────────────────
# from app.utils.config import settings
#
# @app.get("/health")
# async def health():
#     return {
#         "status": "healthy",
#         "app": settings.APP_NAME,
#         "version": settings.APP_VERSION
#     }


# In main.py for server startup:
# ─────────────────────────────────────────────────────────────────────────
# import uvicorn
# from app.utils.config import settings
#
# if __name__ == "__main__":
#     uvicorn.run(
#         "app.main:app",
#         host=settings.HOST,
#         port=settings.PORT,
#         reload=True  # development only
#     )


# For logging configuration:
# ─────────────────────────────────────────────────────────────────────────
# import logging
# from app.utils.config import settings
#
# logging.basicConfig(level=settings.LOG_LEVEL)
# logger = logging.getLogger(__name__)


# ============================================================================
# .env File Format Example
# ============================================================================
# APP_NAME=OPS AI Runbook Assistant
# APP_VERSION=0.1.0
# LOG_LEVEL=INFO
# OLLAMA_BASE_URL=http://localhost:11434
# HOST=0.0.0.0
# PORT=8000
