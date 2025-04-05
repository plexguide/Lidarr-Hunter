#!/usr/bin/env python3
"""
Artist Upgrade Logic
Handles quality cutoff upgrade operations for artists (all albums)
"""

import random
import time
from typing import Dict, List, Set
from utils.logger import logger
from config import MAX_ITEMS, SLEEP_DURATION, MONITORED_ONLY, RANDOM_SELECTION
from api import (
    get_artists_json, get_albums_for_artist, get_quality_profiles, 
    refresh_artist, lidarr_request
)

def get_cutoff_albums() -> Dict[int, List[Dict]]:
    """
    Directly query Lidarr's 'wanted/cutoff' endpoint to get albums below cutoff,
    and organize them by artist.
    
    Returns:
        Dictionary mapping artist IDs to lists of albums needing upgrade
    """
    response = lidarr_request("wanted/cutoff", "GET")
    if not response or not isinstance(response, dict):
        logger.warning("Failed to retrieve cutoff albums from API")
        return {}
    
    records = response.get("records", [])
    if not records:
        logger.info("No cutoff albums returned from API")
        return {}
    
    # Group albums by artist ID
    artists_albums = {}
    for album in records:
        artist_id = album.get("artistId")
        if not artist_id:
            continue
            
        if artist_id not in artists_albums:
            artists_albums[artist_id] = []
            
        artists_albums[artist_id].append(album)
    
    return artists_albums

def get_artist_with_upgrade_albums() -> List[Dict]:
    """
    Get a list of artists who have albums needing upgrade,
    using both the Lidarr API and manual checking.
    
    Returns:
        List of artists with albums needing upgrades
    """
    # Get artists with cutoff albums directly from API
    artists_with_upgrades = []
    artists_cutoff_albums = get_cutoff_albums()
    
    if artists_cutoff_albums:
        # Use direct API results
        logger.info(f"Found {len(artists_cutoff_albums)} artist(s) with albums needing upgrade via API.")
        
        for artist_id, albums in artists_cutoff_albums.items():
            # Get artist details
            artist_data = lidarr_request(f"artist/{artist_id}", "GET")
            if not artist_data:
                continue
                
            # Skip unmonitored artists if MONITORED_ONLY is enabled
            if MONITORED_ONLY and not artist_data.get("monitored", False):
                continue
                
            # Skip if all albums are unmonitored and MONITORED_ONLY is enabled
            if MONITORED_ONLY:
                all_unmonitored = True
                for album in albums:
                    if album.get("monitored", False):
                        all_unmonitored = False
                        break
                if all_unmonitored:
                    continue
            
            # Add artist to candidates list
            artists_with_upgrades.append({
                "artistId": artist_id,
                "artistName": artist_data.get("artistName", "Unknown Artist"),
                "albumCount": len(albums)
            })
    else:
        # Fallback to manual scanning
        logger.info("Falling back to manual artist/album quality check...")
        
        # Get quality profiles
        profiles = get_quality_profiles()
        if not profiles:
            logger.info("No quality profiles available. Cannot determine artists with upgradable albums.")
            return []
            
        # Get all artists
        artists = get_artists_json()
        if not artists:
            logger.error("No artist data available")
            return []
            
        # Check each artist for albums needing upgrade
        for artist in artists:
            if MONITORED_ONLY and not artist.get("monitored", False):
                continue
                
            artist_id = artist["id"]
            artist_name = artist.get("artistName", "Unknown Artist")
            
            # Get the artist's albums
            albums = get_albums_for_artist(artist_id) or []
            upgrade_albums = []
            
            for album in albums:
                if MONITORED_ONLY and not album.get("monitored", False):
                    continue
                    
                # Check for the qualityCutoffNotMet flag
                if album.get("qualityCutoffNotMet", False):
                    upgrade_albums.append(album)
                    continue
                    
                # Otherwise check if album has files but needs quality upgrade
                if album.get("statistics", {}).get("sizeOnDisk", 0) > 0:
                    # Album is fully downloaded
                    track_count = album.get("statistics", {}).get("trackCount", 0)
                    track_file_count = album.get("statistics", {}).get("trackFileCount", 0)
                    
                    if track_count == track_file_count:
                        # Check quality
                        profile_id = album.get("qualityProfileId")
                        if profile_id and profile_id in profiles:
                            profile = profiles[profile_id]
                            cutoff_id = profile.get("cutoff")
                            
                            quality_id = album.get("quality", {}).get("quality", {}).get("id", 0)
                            
                            if isinstance(cutoff_id, int) and isinstance(quality_id, int):
                                if quality_id < cutoff_id:
                                    upgrade_albums.append(album)
            
            # If artist has albums needing upgrade, add to list
            if upgrade_albums:
                artists_with_upgrades.append({
                    "artistId": artist_id,
                    "artistName": artist_name,
                    "albumCount": len(upgrade_albums)
                })
    
    return artists_with_upgrades

def process_artist_upgrades() -> None:
    """
    Scan all artists and initiate a search for all albums 
    that need quality upgrades for each artist
    """
    logger.info("=== Checking for Artist-level Quality Upgrades (Cutoff Unmet) ===")

    # Get artists with albums needing upgrade
    upgrade_candidates = get_artist_with_upgrade_albums()

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
        album_count = artist_obj.get("albumCount", "Unknown")

        logger.info(f"Upgrading {album_count} album(s) for artist '{artist_name}'...")

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