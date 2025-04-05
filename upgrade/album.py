#!/usr/bin/env python3
"""
Album Upgrade Logic
Handles quality cutoff upgrade operations for albums
"""

import random
import time
from typing import Dict, List
from utils.logger import logger
from config import HUNT_UPGRADE_ALBUMS, SLEEP_DURATION, MONITORED_ONLY, RANDOM_SELECTION
from api import refresh_artist, album_search, lidarr_request

def get_cutoff_albums() -> List[Dict]:
    """
    Directly query Lidarr's 'wanted/cutoff' endpoint to get albums below cutoff.
    Simplified to match the curl approach.
    """
    try:
        url = f"{lidarr_request.API_URL}/api/v1/wanted/cutoff"
        headers = {
            "X-Api-Key": lidarr_request.API_KEY,
            "Accept": "application/json",
        }
        params = {
            "pageSize": 100,
            "page": 1
        }
        
        response = lidarr_request.session.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        if not data or not isinstance(data, dict):
            logger.warning("Invalid response format from wanted/cutoff API")
            return []
        
        records = data.get("records", [])
        if not records:
            logger.info("No cutoff albums returned from API")
            return []
        
        # Log the found albums
        for album in records:
            artist_name = album.get("artist", {}).get("artistName", "Unknown Artist")
            album_title = album.get("title", "Unknown Album")
            quality_name = album.get("quality", {}).get("quality", {}).get("name", "Unknown")
            logger.info(f"Found album needing upgrade: {artist_name} - {album_title} [{quality_name}]")
        
        return records
        
    except Exception as e:
        logger.error(f"Error getting cutoff albums: {e}")
        return []
        
def process_album_upgrades() -> None:
    """
    Gets albums with quality below cutoff and initiates searches for better quality.
    """
    logger.info("=== Checking for Album Quality Upgrades (Cutoff Unmet) ===")
    
    # If HUNT_UPGRADE_ALBUMS is set to 0, skip upgrade processing
    if HUNT_UPGRADE_ALBUMS <= 0:
        logger.info("HUNT_UPGRADE_ALBUMS is set to 0, skipping album upgrades")
        return
    
    # Get cutoff albums directly from Lidarr's API
    cutoff_albums = get_cutoff_albums()
    
    if not cutoff_albums:
        logger.info("No albums below cutoff found. No upgrades needed.")
        return

    logger.info(f"Found {len(cutoff_albums)} album(s) needing upgrade.")
    
    # Prepare upgrade candidates with needed information
    upgrade_candidates = []
    for album in cutoff_albums:
        album_id = album.get("id")
        album_title = album.get("title", "Unknown Album")
        artist = album.get("artist", {})
        artist_id = artist.get("id")
        artist_name = artist.get("artistName", "Unknown Artist")
        monitored = album.get("monitored", False)
        
        # Skip albums where we can't get IDs
        if not album_id or not artist_id:
            continue
            
        # Skip unmonitored albums if MONITORED_ONLY is enabled
        if MONITORED_ONLY and not monitored:
            logger.debug(f"Skipping unmonitored album: {artist_name} - {album_title}")
            continue
        
        # Add to upgrade candidates
        upgrade_candidates.append({
            "artistId": artist_id,
            "artistName": artist_name,
            "albumId": album_id,
            "albumTitle": album_title
        })
    
    if not upgrade_candidates:
        logger.info("No monitored albums found for upgrade.")
        return
    
    logger.info(f"Processing {min(HUNT_UPGRADE_ALBUMS, len(upgrade_candidates))} of {len(upgrade_candidates)} candidate album(s) for upgrade")
    
    processed_count = 0
    used_indices = set()

    # Process albums up to HUNT_UPGRADE_ALBUMS
    while True:
        if processed_count >= HUNT_UPGRADE_ALBUMS:
            logger.info(f"Reached HUNT_UPGRADE_ALBUMS={HUNT_UPGRADE_ALBUMS}. Stopping upgrade loop.")
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
            logger.info(f"Processed {processed_count}/{HUNT_UPGRADE_ALBUMS} album upgrades this cycle.")
        else:
            logger.warning(f"WARNING: AlbumSearch failed for album ID={album_id}.")
            time.sleep(10)

        logger.info(f"Sleeping {SLEEP_DURATION}s after upgrade attempt...")
        time.sleep(SLEEP_DURATION)

    logger.info(f"Completed processing {processed_count} album upgrades total in this run.")