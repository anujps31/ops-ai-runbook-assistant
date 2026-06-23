# Logging configuration module
# Provides centralized logging setup for the entire application
# Configures console logging with consistent format across all modules

import logging
from typing import Optional
from app.utils.config import settings


# ============================================================================
# Logging Configuration Constants
# ============================================================================

# Log message format string
# Includes timestamp, log level, module name, and message
# Format: [2024-06-23 10:30:45,123] [INFO] [app.services.incident] Message here
LOG_FORMAT: str = (
    "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
)

# Timestamp format within log messages
# Shows date and time with milliseconds
# Format: 2024-06-23 10:30:45,123
DATETIME_FORMAT: str = "%Y-%m-%d %H:%M:%S"


# ============================================================================
# Configure Root Logger (One-time setup)
# ============================================================================

def _configure_root_logger() -> None:
    """
    Configure the root logger for the entire application
    
    This function is called once at module import time to:
    1. Remove default handlers (avoid duplicate logs)
    2. Create console handler (output to stdout/stderr)
    3. Set log level from configuration
    4. Apply consistent formatting to all logs
    
    Purpose:
        Ensures all loggers in the application have consistent format and level
        without needing to configure each logger individually
    
    Note:
        This is called automatically when this module is imported
    """
    # Get the root logger (parent of all loggers in the application)
    root_logger: logging.Logger = logging.getLogger()
    
    # Remove any existing handlers to prevent duplicate logs
    # (default Python logger adds a handler automatically)
    root_logger.handlers.clear()
    
    # Set the logging level from configuration
    # This controls the minimum severity level for messages to be logged
    root_logger.setLevel(settings.LOG_LEVEL)
    
    # Create a console handler (outputs to terminal/stdout)
    console_handler: logging.StreamHandler = logging.StreamHandler()
    
    # Set the same log level for the console handler
    console_handler.setLevel(settings.LOG_LEVEL)
    
    # Create formatter object that defines message format
    formatter: logging.Formatter = logging.Formatter(
        fmt=LOG_FORMAT,                    # Format string defined above
        datefmt=DATETIME_FORMAT,           # Timestamp format defined above
    )
    
    # Attach formatter to console handler
    # This ensures all console output follows our format
    console_handler.setFormatter(formatter)
    
    # Add console handler to root logger
    # Now all loggers will output to console with our format
    root_logger.addHandler(console_handler)


# ============================================================================
# Public API: get_logger() Function
# ============================================================================

def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get a configured logger instance for a module
    
    This function should be used in every module that needs logging.
    It returns a logger with the module name for easier debugging.
    
    Args:
        name (Optional[str]): Logger name, typically the module name (__name__)
                            If None, returns root logger
    
    Returns:
        logging.Logger: Configured logger instance ready to use
    
    Example:
        # In app/services/incident_service.py
        from app.utils.logger import get_logger
        
        logger = get_logger(__name__)  # Creates logger named "app.services.incident_service"
        
        logger.debug("Processing incident...")
        logger.info(f"Incident {incident_id} processed successfully")
        logger.warning("High memory usage detected")
        logger.error("Failed to connect to database")
        logger.critical("Service shutting down due to error")
    
    Log Levels:
        DEBUG (10):    Detailed diagnostic information, typically enabled only for debugging
        INFO (20):     Confirmation that things are working as expected (default)
        WARNING (30):  Something unexpected happened, or will happen soon
        ERROR (40):    A serious problem, software was not able to do some function
        CRITICAL (50): A serious error, the program itself may fail to continue running
    """
    # Get logger by name (creates new logger if doesn't exist)
    # All loggers with same name share configuration from root logger
    logger: logging.Logger = logging.getLogger(name)
    
    # Logger is now configured via root logger handlers and level
    return logger


# ============================================================================
# Module Initialization
# ============================================================================

# Call the configuration function when this module is imported
# This ensures logging is set up before any module uses get_logger()
_configure_root_logger()


# ============================================================================
# Usage Examples
# ============================================================================

# Example 1: Basic logger setup in a module
# ─────────────────────────────────────────────────────────────────────────
# File: app/services/incident_service.py
# 
# from app.utils.logger import get_logger
# 
# logger = get_logger(__name__)  # Creates logger "app.services.incident_service"
# 
# def process_incident(incident_id: str):
#     logger.info(f"Processing incident: {incident_id}")
#     try:
#         # ... process incident ...
#         logger.info(f"Incident {incident_id} processed successfully")
#     except Exception as e:
#         logger.error(f"Failed to process incident {incident_id}: {str(e)}")


# Example 2: Logging in FastAPI route handlers
# ─────────────────────────────────────────────────────────────────────────
# File: app/routes/incidents.py
# 
# from app.utils.logger import get_logger
# from fastapi import APIRouter
# 
# logger = get_logger(__name__)
# router = APIRouter()
# 
# @router.get("/incidents/{incident_id}")
# async def get_incident(incident_id: str):
#     logger.debug(f"Retrieving incident: {incident_id}")
#     # ... fetch incident ...
#     logger.info(f"Retrieved incident: {incident_id}")
#     return incident


# Example 3: Output example with different log levels
# ─────────────────────────────────────────────────────────────────────────
# Console output when LOG_LEVEL=DEBUG:
# 
# [2024-06-23 10:30:45,123] [DEBUG] [app.services.rag] Querying ChromaDB...
# [2024-06-23 10:30:46,456] [INFO] [app.services.rag] Retrieved 5 runbooks
# [2024-06-23 10:30:47,789] [WARNING] [app.services.llm] Ollama response slow (2.3s)
# [2024-06-23 10:30:48,012] [ERROR] [app.routes.incidents] Database connection failed
# [2024-06-23 10:30:49,345] [CRITICAL] [app.main] Application shutdown initiated
