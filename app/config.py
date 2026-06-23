# Application configuration module
# This module centralizes all environment-based settings using Pydantic
# Configuration is loaded from .env file and environment variables

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables and .env file
    
    BaseSettings automatically:
    - Loads from .env file if it exists
    - Loads from environment variables
    - Validates types (e.g., LOG_LEVEL must be a string)
    - Provides defaults if environment variables are missing
    """
    
    # Application metadata
    APP_NAME: str = "OPS AI Runbook Assistant"
    # Description: Application name displayed in logs, documentation, and monitoring
    # Default: OPS AI Runbook Assistant
    # Environment variable: APP_NAME
    
    APP_VERSION: str = "0.1.0"
    # Description: Semantic version of the application
    # Default: 0.1.0
    # Environment variable: APP_VERSION
    # Used for: API versioning, health checks, monitoring
    
    # Logging configuration
    LOG_LEVEL: str = "INFO"
    # Description: Logging level for the application
    # Default: INFO (standard production level)
    # Allowed values: DEBUG, INFO, WARNING, ERROR, CRITICAL
    # Environment variable: LOG_LEVEL
    # Used for: Controlling verbosity of application logs
    
    # Ollama integration (LLM service)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    # Description: Base URL for Ollama LLM API
    # Default: http://localhost:11434 (standard Ollama local port)
    # Environment variable: OLLAMA_BASE_URL
    # Used for: All LLM inference requests (summarization, analysis, etc.)
    # Example production: https://ollama.production.company.com
    
    class Config:
        """
        Pydantic configuration for Settings class
        
        Attributes:
            env_file: Path to .env file containing environment variables
            env_file_encoding: Character encoding of .env file
            case_sensitive: Whether environment variable names are case-sensitive
        """
        env_file = ".env"              # Look for settings in .env file at project root
        env_file_encoding = "utf-8"    # Standard UTF-8 encoding for .env file
        case_sensitive = False         # Allow both APP_NAME and app_name in .env


@lru_cache()
def get_settings() -> Settings:
    """
    Get application settings with caching
    
    This function is cached so that:
    - Settings are loaded once and reused
    - Environment variables are read once at startup (thread-safe)
    - Subsequent calls return the cached instance
    
    Returns:
        Settings: Singleton instance of application settings
    
    Usage in FastAPI:
        from app.config import get_settings
        
        @app.get("/health")
        async def health(settings: Settings = Depends(get_settings)):
            return {"app": settings.APP_NAME}
    """
    return Settings()


# Example .env file format:
# ===========================
# APP_NAME=OPS AI Runbook Assistant
# APP_VERSION=0.1.0
# LOG_LEVEL=DEBUG
# OLLAMA_BASE_URL=http://localhost:11434
# ===========================
