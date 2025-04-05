#!/usr/bin/env python3
"""
Album Mode Missing Logic
Handles processing for missing content in album mode
"""

import random
import time
from utils.logger import logger
from config import HUNT_MISSING_ITEMS, SLEEP_DURATION, MONITORED_ONLY, RANDOM_SELECTION
from api import get_artists_json, get_albums_for_artist, refresh_artist, album_search

def process_albums_missing() -> None:
    """Process albums with missing tracks"""
    # Skip if HUNT_MISSING_ITEMS is set to 0
    if HUNT_MISSING_ITEMS <= 0:
        logger.info("HUNT_MISSING_ITEMS is set to 0. Skipping missing albums check.")
        return

    logger.info("=== Running in ALBUM MODE (Missing) ===")
    artists = get_artists_json()
    if not artists:
        logger.error("ERROR: No artist data. 60s wait...")
        time.sleep(60)
        return

    incomplete_albums = []

    # Gather all incomplete albums from all artists
    for artist in artists:
        artist_id = artist["id"]
        artist_name = artist.get("artistName", "Unknown Artist")
        artist_monitored = artist.get("monitored", False)

        if MONITORED_ONLY and not artist_monitored:
            continue

        albums = get_albums_for_artist(artist_id) or []
        for alb in albums:
            album_id = alb["id"]
            album_title = alb.get("title", "Unknown Album")
            album_monitored = alb.get("monitored", False)

            if MONITORED_ONLY and not album_monitored:
                continue

            track_count = alb.get("statistics", {}).get("trackCount", 0)
            track_file_count = alb.get("statistics", {}).get("trackFileCount", 0)
            if track_count > track_file_count:
                # incomplete album
                incomplete_albums.append({
                    "artistId": artist_id,
                    "artistName": artist_name,
                    "albumId": album_id,
                    "albumTitle": album_title
                })

    if not incomplete_albums:
        logger.info("No incomplete albums found. 60s wait...")
        time.sleep(60)
        return

    logger.info(f"Found {len(incomplete_albums)} incomplete album(s).")
    processed_count = 0
    used_indices = set()

    # Process albums up to HUNT_MISSING_ITEMS
    while True:
        if HUNT_MISSING_ITEMS > 0 and processed_count >= HUNT_MISSING_ITEMS:
            logger.info(f"Reached HUNT_MISSING_ITEMS ({HUNT_MISSING_ITEMS}). Exiting loop.")
            break
        if len(used_indices) >= len(incomplete_albums):
            logger.info("All incomplete albums processed. Exiting loop.")
            break

        # Select next album (randomly or sequentially)
        if RANDOM_SELECTION and len(incomplete_albums) > 1:
            while True:
                idx = random.randint(0, len(incomplete_albums) - 1)
                if idx not in used_indices:
                    break
        else:
            idx_candidates = [i for i in range(len(incomplete_albums)) if i not in used_indices]
            if not idx_candidates:
                break
            idx = idx_candidates[0]

        used_indices.add(idx)
        album_obj = incomplete_albums[idx]
        artist_id = album_obj["artistId"]
        artist_name = album_obj["artistName"]
        album_id = album_obj["albumId"]
        album_title = album_obj["albumTitle"]

        logger.info(f"Processing incomplete album '{album_title}' by '{artist_name}'...")

        # Refresh the artist
        refresh_resp = refresh_artist(artist_id)
        if not refresh_resp or "id" not in refresh_resp:
            logger.warning(f"WARNING: Could not refresh artist {artist_name}. Skipping album.")
            time.sleep(10)
            continue
        logger.info(f"Refresh command accepted (ID={refresh_resp['id']}). Waiting 5s...")
        time.sleep(5)

        # AlbumSearch
        search_resp = album_search(album_id)
        if search_resp and "id" in search_resp:
            logger.info(f"AlbumSearch command accepted (ID={search_resp['id']}).")
        else:
            logger.warning(f"WARNING: AlbumSearch command failed for album '{album_title}'.")

        processed_count += 1
        logger.info(f"Album processed. Sleeping {SLEEP_DURATION}s...")
        time.sleep(SLEEP_DURATION)