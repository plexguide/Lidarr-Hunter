#!/usr/bin/env python3
"""
Configuration module for Huntarr-Lidarr
Handles all environment variables and configuration settings
"""

import os
import logging

# API Configuration
API_KEY = os.environ.get("API_KEY", "your-api-key")
API_URL = os.environ.get("API_URL", "http://your-lidarr-address:8686")

# Missing Items Settings
try:
    HUNT_MISSING_ITEMS = int(os.environ.get("HUNT_MISSING_ITEMS", "1"))
except ValueError:
    HUNT_MISSING_ITEMS = 1
    print(f"[WARN] Invalid HUNT_MISSING_ITEMS value; using default {HUNT_MISSING_ITEMS}")

# Upgrade Albums Settings
try:
    HUNT_UPGRADE_ALBUMS = int(os.environ.get("HUNT_UPGRADE_ALBUMS", "0"))
except ValueError:
    HUNT_UPGRADE_ALBUMS = 0
    print(f"[WARN] Invalid HUNT_UPGRADE_ALBUMS value; using default {HUNT_UPGRADE_ALBUMS}")

# Sleep duration in seconds after completing each item (default 900 = 15 minutes)
try:
    SLEEP_DURATION = int(os.environ.get("SLEEP_DURATION", "900"))
except ValueError:
    SLEEP_DURATION = 900
    print(f"[WARN] Invalid SLEEP_DURATION value; using default {SLEEP_DURATION}")

# Selection Settings
RANDOM_SELECTION = os.environ.get("RANDOM_SELECTION", "true").lower() == "true"
MONITORED_ONLY = os.environ.get("MONITORED_ONLY", "true").lower() == "true"

# Search Configuration
# HUNT_MISSING_MODE: "artist", "album", or "both" (for missing content search)
HUNT_MISSING_MODE = os.environ.get("HUNT_MISSING_MODE", "artist")

# Debug Settings
DEBUG_MODE = os.environ.get("DEBUG_MODE", "false").lower() == "true"

def log_configuration(logger):
    """Log the current configuration settings"""
    logger.info("=== Huntarr [Lidarr Edition] Starting ===")
    logger.info(f"API URL: {API_URL}")
    logger.info(f"Missing Items: HUNT_MISSING_ITEMS={HUNT_MISSING_ITEMS}, HUNT_MISSING_MODE={HUNT_MISSING_MODE}")
    logger.info(f"Upgrade Albums: HUNT_UPGRADE_ALBUMS={HUNT_UPGRADE_ALBUMS}")
    logger.info(f"Other Settings: SLEEP_DURATION={SLEEP_DURATION}s, MONITORED_ONLY={MONITORED_ONLY}, RANDOM_SELECTION={RANDOM_SELECTION}")
    logger.debug(f"API_KEY={API_KEY}")