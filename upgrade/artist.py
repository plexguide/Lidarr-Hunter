#!/usr/bin/env python3
"""
Artist Upgrade Logic
Handles quality cutoff upgrade operations for artists (all albums)
"""

import random
import time
from typing import Dict, List
from utils.logger import logger
from config import MAX_ITEMS, SLEEP_DURATION, MONITORED_ONLY, RANDOM_SELECTION
from api import (
    get_artists_json, get_albums_for_artist, get_quality_profiles, 
    refresh_artist, lidarr_request
)

def get_artist_upgrade_status(artist_id: int, profiles: Dict[int, Dict]) -> bool:
    """
    Check if an artist has any albums that need upgrades
    
    Args:
        artist_id: Lidarr artist ID
        profiles: Dictionary of quality profiles keyed by profile ID
        
    Returns:
        True if any album needs a quality upgrade, False otherwise
    """
    albums = get_albums_for_artist(artist_id) or []
    for album in albums:
        if MONITORED_ONLY and not album.get("monitored", False):
            continue
            
        if not album.get("statistics", {}).get("sizeOnDisk", 0) > 0:
            # Skip albums with no files on disk
            continue
            
        profile_id = album.get("qualityProfileId")
        if not profile_id or profile_id not in profiles:
            continue
            
        profile = profiles[profile_id]
        cutoff_id = profile.get("cutoff")
        
        # Get the album's quality info
        album_quality = album.get("quality", {})
        if not album_quality:
            continue
            
        album_quality_id = album_quality.get("quality", {}).get("id", 0)
        
        if isinstance(cutoff_id, int) and isinstance(album_quality_id, int):
            if album_quality_id < cutoff_id:
                return True
                
    return False

def process_artist_upgrades() -> None:
    """
    Scan all artists and initiate a search for all albums 
    that need quality upgrades for each artist
    """
    logger.info("=== Checking for Artist-level Quality Upgrades (Cutoff Unmet) ===")

    # 1) Retrieve all quality profiles
    profiles = get_quality_profiles()
    if not profiles:
        logger.info("No quality profiles available. Cannot determine cutoff unmet artists.")
        return

    # 2) Retrieve all artists
    artists = get_artists_json()
    if not artists:
        logger.error("No artist data. Cannot process upgrades.")
        return

    # 3) Collect all artists with albums needing upgrade
    upgrade_candidates = []
    for artist in artists:
        if MONITORED_ONLY and not artist.get("monitored", False):
            continue

        artist_id = artist["id"]
        artist_name = artist.get("artistName", "Unknown Artist")
        
        # Check if artist has any albums needing upgrade
        if get_artist_upgrade_status(artist_id, profiles):
            upgrade_candidates.append({
                "artistId": artist_id,
                "artistName": artist_name
            })

    if not upgrade_candidates:
        logger.info("No artists with albums below cutoff found. No upgrades needed.")
        return

    logger.info(f"Found {len(upgrade_candidates)} artist(s) with albums needing upgrade.")
    processed_count = 0
    used_indices = set()

    # Process artists up to MAX_ITEMS
    while True:
        if MAX_ITEMS > 0 and processed_count >= MAX_ITEMS:
            logger.info(f"Reached MAX_ITEMS={MAX_ITEMS}. Stopping upgrade loop.")
            break
        if len(used_indices) >= len(upgrade_candidates):
            logger.info("All upgrade candidates processed.")
            break

        # Select next artist (randomly or sequentially)
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
        artist_obj = upgrade_candidates[idx]
        artist_id = artist_obj["artistId"]
        artist_name = artist_obj["artistName"]

        logger.info(f"Upgrading albums for artist '{artist_name}'...")

        # Refresh the artist first
        ref_resp = refresh_artist(artist_id)
        if not ref_resp or "id" not in ref_resp:
            logger.warning(f"WARNING: Refresh command failed for artist {artist_name}. Skipping.")
            time.sleep(10)
            continue
        logger.info(f"Refresh accepted (ID={ref_resp['id']}). Waiting 5s...")
        time.sleep(5)

        # Perform AlbumSearch at the artist level to search for all albums
        data = {
            "name": "AlbumSearch",
            "artistIds": [artist_id]
        }
        
        srch_resp = lidarr_request("command", method="POST", data=data)
        if srch_resp and "id" in srch_resp:
            logger.info(f"AlbumSearch command for artist accepted (ID={srch_resp['id']}).")
            processed_count += 1
            logger.info(f"Processed {processed_count}/{MAX_ITEMS} artist upgrades this cycle.")
        else:
            logger.warning(f"WARNING: AlbumSearch failed for artist ID={artist_id}.")
            time.sleep(10)

        logger.info(f"Sleeping {SLEEP_DURATION}s after upgrade attempt...")
        time.sleep(SLEEP_DURATION)

    logger.info(f"Completed processing {processed_count} artist upgrades total in this run.")