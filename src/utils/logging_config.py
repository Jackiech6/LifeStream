"""Logging configuration for LifeStream."""

import logging
import sys
from pathlib import Path
from typing import Optional
from config.settings import Settings


def setup_logging(settings: Optional[Settings] = None) -> logging.Logger:
    """Set up logging configuration.
    
    Args:
        settings: Application settings. If None, creates default settings.
        
    Returns:
        Configured logger instance.
    """
    if settings is None:
        settings = Settings()
    
    # Create logger
    logger = logging.getLogger("lifestream")
    logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    
    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()
    
    # Create formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler (if log_file is specified)
    if settings.log_file:
        log_path = Path(settings.log_file).expanduser()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_path)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


def get_logger(name: str = "lifestream") -> logging.Logger:
    """Get a logger instance.
    
    Args:
        name: Logger name. Defaults to "lifestream".
        
    Returns:
        Logger instance.
    """
    return logging.getLogger(name)
