#!/usr/bin/env python3
"""
Track Upgrade Logic
Handles quality cutoff upgrade operations for tracks
"""

import random
import time
from typing import Dict
from utils.logger import logger
from config import MAX_ITEMS, SLEEP_DURATION, MONITORED_ONLY, RANDOM_SELECTION
from api import (
    get_artists_json, get_albums_for_artist, get_tracks_for_album, 
    get_quality_profiles, refresh_artist, track_search
)

def track_needs_upgrade(track: Dict, profiles: Dict[int, Dict]) -> bool:
    """
    Determine if a track's current quality is below its profile's cutoff.
    
    Args:
        track: Track data dictionary from Lidarr API
        profiles: Dictionary of quality profiles keyed by profile ID
        
    Returns:
        True if the track needs a quality upgrade, False otherwise
    """
    if not track.get("hasFile", False):
        # If the track has no file, it's missing (not an "upgrade" scenario).
        return False

    profile_id = track.get("qualityProfileId")
    if not profile_id or profile_id not in profiles:
        return False

    profile = profiles[profile_id]
    cutoff_id = profile.get("cutoff")  # The 'cutoff' is typically an integer ID

    # The track's current quality ID
    track_qual_data = track.get("quality", {}).get("quality", {})
    track_current_id = track_qual_data.get("id", 0)

    if isinstance(cutoff_id, int) and isinstance(track_current_id, int):
        return track_current_id < cutoff_id
    return False

def process_cutoff_upgrades() -> None:
    """
    Scans the entire library (artists -> albums -> tracks),
    checks if each track is below cutoff, and calls track_search if so.
    """
    logger.info("=== Checking for Quality Upgrades (Cutoff Unmet) ===")

    # 1) Retrieve all quality profiles
    profiles = get_quality_profiles()
    if not profiles:
        logger.info("No quality profiles available. Cannot determine cutoff unmet tracks.")
        return

    # 2) Retrieve all artists
    artists = get_artists_json()
    if not artists:
        logger.error("No artist data. Cannot process upgrades.")
        return

    # 3) Collect all tracks needing upgrade
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

            album_id = alb["id"]
            album_title = alb.get("title", "Unknown Album")

            tracks = get_tracks_for_album(album_id) or []
            for trk in tracks:
                # If MONITORED_ONLY, skip unmonitored tracks
                if MONITORED_ONLY and not trk.get("monitored", False):
                    continue

                # If track is below cutoff => add to upgrade_candidates
                if track_needs_upgrade(trk, profiles):
                    upgrade_candidates.append({
                        "artistId": artist_id,
                        "artistName": artist_name,
                        "albumId": album_id,
                        "albumTitle": album_title,
                        "trackId": trk["id"],
                        "trackTitle": trk.get("title", "Unknown Track"),
                    })

    if not upgrade_candidates:
        logger.info("No tracks below cutoff found. No upgrades needed.")
        return

    logger.info(f"Found {len(upgrade_candidates)} track(s) needing upgrade.")
    processed_count = 0
    used_indices = set()

    # Process tracks up to MAX_ITEMS
    while True:
        if MAX_ITEMS > 0 and processed_count >= MAX_ITEMS:
            logger.info(f"Reached MAX_ITEMS={MAX_ITEMS}. Stopping upgrade loop.")
            break
        if len(used_indices) >= len(upgrade_candidates):
            logger.info("All upgrade candidates processed.")
            break

        # Select next track (randomly or sequentially)
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
        trk_obj = upgrade_candidates[idx]
        artist_id = trk_obj["artistId"]
        artist_name = trk_obj["artistName"]
        album_id = trk_obj["albumId"]
        album_title = trk_obj["albumTitle"]
        track_id = trk_obj["trackId"]
        track_title = trk_obj["trackTitle"]

        logger.info(f"Upgrading track '{track_title}' from album '{album_title}' by '{artist_name}'...")

        # Refresh the artist first
        ref_resp = refresh_artist(artist_id)
        if not ref_resp or "id" not in ref_resp:
            logger.warning("WARNING: Refresh command failed. Skipping this track.")
            time.sleep(10)
            continue
        logger.info(f"Refresh accepted (ID={ref_resp['id']}). Waiting 5s...")
        time.sleep(5)

        # Perform track search for the new/better quality
        srch_resp = track_search(track_id)
        if srch_resp and "id" in srch_resp:
            logger.info(f"TrackSearch command accepted (ID={srch_resp['id']}).")
            processed_count += 1
            logger.info(f"Processed {processed_count}/{MAX_ITEMS} upgrades this cycle.")
        else:
            logger.warning(f"WARNING: TrackSearch failed for track ID={track_id}.")
            time.sleep(10)

        logger.info(f"Sleeping {SLEEP_DURATION}s after upgrade attempt...")
        time.sleep(SLEEP_DURATION)

    logger.info(f"Completed processing {processed_count} upgrade tracks total in this run.")