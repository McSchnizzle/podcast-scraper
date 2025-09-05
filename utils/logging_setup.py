#!/usr/bin/env python3
"""
Centralized logging configuration for podcast scraper system.
Provides idempotent logging setup with controlled verbosity levels.
"""

import logging
import os
from typing import Optional


def configure_logging() -> None:
    """
    Configure root logging with idempotent behavior.
    Call this once at process start in main entry points.
    
    Environment Variables:
        LOG_LEVEL: Logging level (DEBUG, INFO, WARNING, ERROR) - default INFO
        HTTP_LOG_LEVEL: Level for HTTP libraries (default WARNING)
    """
    root = logging.getLogger()
    
    # Idempotent - only configure once
    if getattr(root, '_configured', False):
        return
    
    # Set logging level from environment
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    
    # Configure root logger with simple format
    logging.basicConfig(
        level=level,
        format="%(levelname)s:%(name)s:%(message)s",
        force=True  # Override any existing configuration
    )
    
    # Quiet down noisy HTTP and API libraries
    http_log_level = os.getenv("HTTP_LOG_LEVEL", "WARNING").upper()
    noisy_loggers = [
        "httpx",
        "urllib3", 
        "openai",
        "requests",
        "feedparser",
        "anthropic"
    ]
    
    for logger_name in noisy_loggers:
        logging.getLogger(logger_name).setLevel(http_log_level)
    
    # Mark as configured to prevent reconfiguration
    root._configured = True
    
    # Log configuration status in DEBUG mode
    if level == "DEBUG":
        root.debug(f"🔧 Logging configured: level={level}, http_level={http_log_level}")


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get a logger instance for a module.
    Ensures logging is configured first.
    
    Args:
        name: Logger name (uses caller's __name__ if not provided)
    
    Returns:
        logging.Logger: Configured logger instance
    """
    # Ensure logging is configured
    configure_logging()
    
    # Return logger for the specified name
    return logging.getLogger(name)


def set_verbose(enabled: bool = True) -> None:
    """
    Enable or disable verbose logging.
    
    Args:
        enabled: True to enable DEBUG level, False for INFO level
    """
    level = "DEBUG" if enabled else "INFO"
    os.environ["LOG_LEVEL"] = level
    
    # Reconfigure logging with new level
    root = logging.getLogger()
    root.setLevel(level)
    
    if enabled:
        root.debug("🔧 Verbose logging enabled")
    else:
        root.info("🔇 Verbose logging disabled")


def quiet_noisy_libs() -> None:
    """
    Additional function to quiet specific libraries during operations.
    Can be called anytime to reduce noise from third-party libraries.
    """
    extra_noisy = [
        "charset_normalizer",
        "asyncio",
        "websockets",
        "aiohttp",
        "certifi"
    ]
    
    for logger_name in extra_noisy:
        logging.getLogger(logger_name).setLevel(logging.WARNING)