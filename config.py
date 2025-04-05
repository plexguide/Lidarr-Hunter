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

# Processing Settings
try:
    MAX_ITEMS = int(os.environ.get("MAX_ITEMS", "1"))
except ValueError:
    MAX_ITEMS = 1
    print(f"[WARN] Invalid MAX_ITEMS value; using default {MAX_ITEMS}")

try:
    SLEEP_DURATION = int(os.environ.get("SLEEP_DURATION", "900"))
except ValueError:
    SLEEP_DURATION = 900
    print(f"[WARN] Invalid SLEEP_DURATION value; using default {SLEEP_DURATION}")

# Selection Settings
RANDOM_SELECTION = os.environ.get("RANDOM_SELECTION", "true").lower() == "true"
MONITORED_ONLY = os.environ.get("MONITORED_ONLY", "true").lower() == "true"

# Search Configuration
# SEARCH_MODE: "artist" or "album" (applies to both missing and upgrade logic)
SEARCH_MODE = os.environ.get("SEARCH_MODE", "artist")

# SEARCH_TYPE: "missing", "upgrade", or "both"
# - "missing" => only missing items
# - "upgrade" => only cutoff unmet upgrades
# - "both"    => missing items first, then upgrades
SEARCH_TYPE = os.environ.get("SEARCH_TYPE", "missing")

# Debug Settings
DEBUG_MODE = os.environ.get("DEBUG_MODE", "false").lower() == "true"

def log_configuration(logger):
    """Log the current configuration settings"""
    logger.info("=== Huntarr [Lidarr Edition] Starting ===")
    logger.info(f"API URL: {API_URL}")
    logger.info(f"Configuration: MAX_ITEMS={MAX_ITEMS}, SLEEP_DURATION={SLEEP_DURATION}s")
    logger.info(f"MONITORED_ONLY={MONITORED_ONLY}, RANDOM_SELECTION={RANDOM_SELECTION}")
    logger.info(f"SEARCH_MODE={SEARCH_MODE}, SEARCH_TYPE={SEARCH_TYPE}")
    logger.debug(f"API_KEY={API_KEY}")
