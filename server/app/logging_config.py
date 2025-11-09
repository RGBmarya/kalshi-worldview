"""
Logging configuration for the application.
"""
import logging
import sys
from rich.logging import RichHandler


def setup_logging(level: str = "INFO"):
    """
    Set up logging with rich formatting.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    # Remove any existing handlers
    root = logging.getLogger()
    for handler in root.handlers[:]:
        root.removeHandler(handler)
    
    # Configure rich handler
    handler = RichHandler(
        rich_tracebacks=True,
        tracebacks_show_locals=True,
        markup=True,
    )
    
    # Set format
    handler.setFormatter(
        logging.Formatter(
            "%(message)s",
            datefmt="[%X]",
        )
    )
    
    # Configure root logger
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[handler],
    )
    
    # Set level for our app modules
    logging.getLogger("app").setLevel(level)
    
    # Reduce noise from other libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger for a module."""
    return logging.getLogger(f"app.{name}")


