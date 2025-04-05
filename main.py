#!/usr/bin/env python3
"""
Huntarr [Lidarr Edition] - Python Version
Main entry point for the application
"""

import time
import sys
from utils.logger import logger
from config import SEARCH_MODE, SEARCH_TYPE, log_configuration
from missing.artist import process_artists_missing
from missing.album import process_albums_missing
from upgrade.album import process_album_upgrades
from upgrade.artist import process_artist_upgrades

def main_loop() -> None:
    """Main processing loop for Huntarr-Lidarr"""
    while True:
        logger.info(f"=== Starting Huntarr-Lidarr cycle (MODE={SEARCH_MODE}, TYPE={SEARCH_TYPE}) ===")

        # 1) If "missing" or "both", handle missing logic first
        if SEARCH_TYPE in ["missing", "both"]:
            if SEARCH_MODE == "artist":
                process_artists_missing()
            elif SEARCH_MODE == "album":
                process_albums_missing() 
            else:
                logger.warning(f"Unknown SEARCH_MODE={SEARCH_MODE}; defaulting to artist missing.")
                process_artists_missing()

        # 2) If "upgrade" or "both", handle upgrade logic 
        if SEARCH_TYPE in ["upgrade", "both"]:
            if SEARCH_MODE == "artist":
                process_artist_upgrades()
            elif SEARCH_MODE == "album":
                process_album_upgrades()
            else:
                logger.warning(f"Unknown SEARCH_MODE={SEARCH_MODE} for upgrades; defaulting to artist.")
                process_artist_upgrades()

        logger.info("Cycle complete. Waiting 60s before next cycle...")
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