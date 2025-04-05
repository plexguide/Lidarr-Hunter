#!/usr/bin/env python3
"""
Both Missing Modes Logic
Handles processing for missing content in both artist and album modes
"""

from utils.logger import logger
from missing.artist import process_artists_missing
from missing.album import process_albums_missing

def process_both_missing():
    """
    Process missing content in both artist and album modes.
    First runs artist mode, then album mode.
    """
    logger.info("=== Running in BOTH MODES (Missing) ===")
    logger.info("First, processing artists with missing content...")
    
    # Run artist missing process
    process_artists_missing()
    
    logger.info("Now, processing albums with missing content...")
    
    # Run album missing process
    process_albums_missing()
    
    logger.info("Completed both missing modes.")