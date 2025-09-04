#!/usr/bin/env python3
"""
Centralized Logging Configuration for Podcast Scraper System
Provides unified logging setup with verbose/quiet modes
"""

import logging
import sys
from typing import Optional

def setup_logging(verbose: bool = False, logger_name: Optional[str] = None) -> logging.Logger:
    """
    Set up centralized logging configuration
    
    Args:
        verbose: Enable DEBUG level logging if True, otherwise INFO level
        logger_name: Name for the logger (uses __name__ if not provided)
    
    Returns:
        Configured logger instance
    """
    # Set root logging level
    level = logging.DEBUG if verbose else logging.INFO
    
    # Configure root logger
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Get logger for the calling module
    logger = logging.getLogger(logger_name or __name__)
    
    # Configure external library loggers to be quieter unless verbose
    if not verbose:
        # Quiet down httpx/requests logs
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("requests").setLevel(logging.WARNING)
        
        # Quiet down other commonly chatty libraries
        logging.getLogger("openai").setLevel(logging.WARNING)
        logging.getLogger("feedparser").setLevel(logging.WARNING)
    else:
        logger.debug("🔧 Verbose logging enabled")
    
    return logger

def configure_module_logger(module_name: str, verbose: bool = False) -> logging.Logger:
    """
    Configure a logger for a specific module
    
    Args:
        module_name: Name of the module (typically __name__)
        verbose: Enable verbose logging
    
    Returns:
        Configured logger for the module
    """
    logger = logging.getLogger(module_name)
    
    if verbose:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
    
    return logger

def set_httpx_quiet():
    """Specifically quiet httpx logs to WARNING level"""
    logging.getLogger("httpx").setLevel(logging.WARNING)

def set_all_quiet():
    """Set all external libraries to WARNING level"""
    external_libs = [
        "httpx", "urllib3", "requests", "openai", 
        "feedparser", "elevenlabs", "youtube_transcript_api"
    ]
    
    for lib in external_libs:
        logging.getLogger(lib).setLevel(logging.WARNING)

# Convenience function for backward compatibility
def get_logger(name: str, verbose: bool = False) -> logging.Logger:
    """Get a configured logger for a module"""
    return configure_module_logger(name, verbose)