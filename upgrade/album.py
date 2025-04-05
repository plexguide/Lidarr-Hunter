#!/usr/bin/env python3
"""
Album Upgrade Logic
Handles quality cutoff upgrade operations for albums
"""

import random
import time
from typing import Dict, List
from utils.logger import logger
from config import MAX_ITEMS, SLEEP_DURATION, MONITORED_ONLY, RANDOM_SELECTION
from api import (
    get_artists_json, get_albums_for_artist, get_quality_profiles, 
    refresh_artist, album_search
)

def album_needs_upgrade(album: Dict, profiles: Dict[int, Dict]) -> bool:
    """
    Determine if an album's current quality is below its profile's cutoff.
    
    Args:
        album: Album data dictionary from Lidarr API
        profiles: Dictionary of quality profiles keyed by profile ID
        
    Returns:
        True if the album needs a quality upgrade, False otherwise
    """
    if not album.get("statistics", {}).get("sizeOnDisk", 0) > 0:
        # If the album has no files on disk, it's missing (not an "upgrade" scenario)
        return False

    profile_id = album.get("qualityProfileId")
    if not profile_id or profile_id not in profiles:
        return False
        
    profile = profiles[profile_id]
    cutoff_id = profile.get("cutoff")  # The 'cutoff' is typically an integer ID
    
    # Get the album's quality items
    album_quality = album.get("quality", {})
    if not album_quality:
        return False
        
    # Check if any quality item is below cutoff
    album_quality_id = album_quality.get("quality", {}).get("id", 0)
    
    if isinstance(cutoff_id, int) and isinstance(album_quality_id, int):
        return album_quality_id < cutoff_id
    return False

def process_album_upgrades() -> None:
    """
    Scans all albums to find those with quality below cutoff,
    and initiates a search for better quality.
    """
    logger.info("=== Checking for Album Quality Upgrades (Cutoff Unmet) ===")

    # 1) Retrieve all quality profiles
    profiles = get_quality_profiles()
    if not profiles:
        logger.info("No quality profiles available. Cannot determine cutoff unmet albums.")
        return

    # 2) Retrieve all artists
    artists = get_artists_json()
    if not artists:
        logger.error("No artist data. Cannot process upgrades.")
        return

    # 3) Collect all albums needing upgrade
    upgrade_candidates = []
    for artist in artists:
        if MONITORED_ONLY and not artist.get("monitored", False):
            continue

        artist_id = artist["id"]
        artist_name = artist.get("artistName", "Unknown Artist")

        albums = get_albums_for_artist(artist_id) or []
        for alb in albums:
            if MONITORED_ONLY and not alb.get("monitored", False):
                continue

            # Check if album needs upgrade
            if album_needs_upgrade(alb, profiles):
                upgrade_candidates.append({
                    "artistId": artist_id,
                    "artistName": artist_name,
                    "albumId": alb["id"],
                    "albumTitle": alb.get("title", "Unknown Album")
                })

    if not upgrade_candidates:
        logger.info("No albums below cutoff found. No upgrades needed.")
        return

    logger.info(f"Found {len(upgrade_candidates)} album(s) needing upgrade.")
    processed_count = 0
    used_indices = set()

    # Process albums up to MAX_ITEMS
    while True:
        if MAX_ITEMS > 0 and processed_count >= MAX_ITEMS:
            logger.info(f"Reached MAX_ITEMS={MAX_ITEMS}. Stopping upgrade loop.")
            break
        if len(used_indices) >= len(upgrade_candidates):
            logger.info("All upgrade candidates processed.")
            break

        # Select next album (randomly or sequentially)
        if RANDOM_SELECTION and len(upgrade_candidates) > 1:
            while True:
                idx = random.randint(0, len(upgrade_candidates) - 1)
                if idx not in used_indices:
                    break
        else:
            idx_candidates = [i for i in range(len(upgrade_candidates)) if i not in used_indices]
            if not idx_candidates:
                break
            idx = idx_candidates[0]

        used_indices.add(idx)
        album_obj = upgrade_candidates[idx]
        artist_id = album_obj["artistId"]
        artist_name = album_obj["artistName"]
        album_id = album_obj["albumId"]
        album_title = album_obj["albumTitle"]

        logger.info(f"Upgrading album '{album_title}' by '{artist_name}'...")

        # Refresh the artist first
        ref_resp = refresh_artist(artist_id)
        if not ref_resp or "id" not in ref_resp:
            logger.warning("WARNING: Refresh command failed. Skipping this album.")
            time.sleep(10)
            continue
        logger.info(f"Refresh accepted (ID={ref_resp['id']}). Waiting 5s...")
        time.sleep(5)

        # Perform album search for better quality
        srch_resp = album_search(album_id)
        if srch_resp and "id" in srch_resp:
            logger.info(f"AlbumSearch command accepted (ID={srch_resp['id']}).")
            processed_count += 1
            logger.info(f"Processed {processed_count}/{MAX_ITEMS} album upgrades this cycle.")
        else:
            logger.warning(f"WARNING: AlbumSearch failed for album ID={album_id}.")
            time.sleep(10)

        logger.info(f"Sleeping {SLEEP_DURATION}s after upgrade attempt...")
        time.sleep(SLEEP_DURATION)

    logger.info(f"Completed processing {processed_count} album upgrades total in this run.")