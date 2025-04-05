#!/usr/bin/env python3
"""
Huntarr [Lidarr Edition] - Python Version
Main entry point for the application
"""

import time
import sys
from utils.logger import logger
from config import HUNT_MISSING_MODE, log_configuration
from missing.artist import process_artists_missing
from missing.album import process_albums_missing 
from upgrade.album import process_album_upgrades

def main_loop() -> None:
    """Main processing loop for Huntarr-Lidarr"""
    while True:
        logger.info(f"=== Starting Huntarr-Lidarr cycle ===")

        # 1) Handle missing content based on HUNT_MISSING_MODE
        if HUNT_MISSING_MODE == "artist" or HUNT_MISSING_MODE == "both":
            process_artists_missing()
            
        if HUNT_MISSING_MODE == "album" or HUNT_MISSING_MODE == "both":
            process_albums_missing()
            
        # 2) Handle album upgrade processing
        process_album_upgrades()

        logger.info("Cycle complete. Waiting 60s before next cycle...")
        logger.info("⭐ Tool Great? Donate @ https://donate.plex.one for Daughter's College Fund!")
        time.sleep(60)

if __name__ == "__main__":
    # Log configuration settings
    log_configuration(logger)

    try:
        main_loop()
    except KeyboardInterrupt:
        logger.info("Huntarr-Lidarr stopped by user.")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        sys.exit(1)