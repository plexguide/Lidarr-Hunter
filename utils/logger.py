#!/usr/bin/env python3
"""
Logging configuration for Huntarr-Lidarr
"""

import logging
import sys
import os

# Get DEBUG_MODE from environment
DEBUG_MODE = os.environ.get("DEBUG_MODE", "false").lower() == "true"

def setup_logger():
    """Configure and return the application logger"""
    logger = logging.getLogger("huntarr-lidarr")
    
    # Set the log level based on DEBUG_MODE
    logger.setLevel(logging.DEBUG if DEBUG_MODE else logging.INFO)
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if DEBUG_MODE else logging.INFO)
    
    # Set format
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(formatter)
    
    # Add handler to logger
    logger.addHandler(console_handler)
    
    return logger

# Create the logger instance
logger = setup_logger()