#!/usr/bin/env python3
"""
Logging configuration for Huntarr-Lidarr
"""

import logging
from config import DEBUG_MODE

def setup_logger():
    """Configure and return the application logger"""
    logging.basicConfig(
        level=logging.DEBUG if DEBUG_MODE else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    return logging.getLogger("huntarr-lidarr")

# Create the logger instance
logger = setup_logger()