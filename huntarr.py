#!/usr/bin/env python3
"""
Huntarr [Lidarr Edition] - Python Version

"""

import os
import time
import json
import random
import logging
import requests
from typing import List, Dict, Any, Optional

# ---------------------------
# Environment Variables
# ---------------------------

API_KEY = os.environ.get("API_KEY", "your-api-key")
API_URL = os.environ.get("API_URL", "http://your-lidarr-address:8686")

# How many items (artists or albums) to process per cycle for MISSING
try:
    MAX_ITEMS = int(os.environ.get("MAX_ITEMS", "1"))
except ValueError:
    MAX_ITEMS = 1
    print(f"[WARN] Invalid MAX_ITEMS value; using default {MAX_ITEMS}")

# Sleep duration in seconds after completing each item (default 900 = 15 minutes)
try:
    SLEEP_DURATION = int(os.environ.get("SLEEP_DURATION", "900"))
except ValueError:
    SLEEP_DURATION = 900
    print(f"[WARN] Invalid SLEEP_DURATION value; using default {SLEEP_DURATION}")

# If True, pick items randomly; if False, go in order
RANDOM_SELECTION = os.environ.get("RANDOM_SELECTION", "true").lower() == "true"

# If MONITORED_ONLY=true, only process monitored artists/albums/tracks
MONITORED_ONLY = os.environ.get("MONITORED_ONLY", "true").lower() == "true"

# SEARCH_MODE: "artist" or "album" (for missing logic)
SEARCH_MODE = os.environ.get("SEARCH_MODE", "artist")

# SEARCH_TYPE: "missing", "upgrade", or "both"
# - "missing" => only missing items
# - "upgrade" => only cutoff unmet upgrades
# - "both"    => missing items first, then upgrades
SEARCH_TYPE = os.environ.get("SEARCH_TYPE", "missing")

# Enable debug logging
DEBUG_MODE = os.environ.get("DEBUG_MODE", "false").lower() == "true"

logging.basicConfig(
    level=logging.DEBUG if DEBUG_MODE else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("huntarr-lidarr")


# ---------------------------
# Lidarr API Helper Functions
# ---------------------------

def lidarr_request(endpoint: str, method: str = "GET", data: Dict = None) -> Optional[Any]:
    """
    Perform a request to the Lidarr API (v1).
    Example endpoint: "artist", "album", "track", "command", or "qualityprofile".
    """
    url = f"{API_URL}/api/v1/{endpoint}"
    headers = {
        "X-Api-Key": API_KEY,
        "Content-Type": "application/json",
    }
    try:
        if method.upper() == "GET":
            resp = requests.get(url, headers=headers, timeout=30)
        else:  # Typically "POST"
            resp = requests.post(url, headers=headers, json=data, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        logger.error(f"API request error to {url}: {e}")
        return None

def get_artists_json() -> Optional[List[Dict]]:
    return lidarr_request("artist", "GET")

def get_albums_for_artist(artist_id: int) -> Optional[List[Dict]]:
    return lidarr_request(f"album?artistId={artist_id}", "GET")

def get_tracks_for_album(album_id: int) -> Optional[List[Dict]]:
    return lidarr_request(f"track?albumId={album_id}", "GET")

def get_quality_profiles() -> Dict[int, Dict]:
    """
    Returns a dict like:
      { profileId: { 'id': <id>, 'name': <str>, 'cutoff': <int>, 'items': [ ... ] }, ... }
    
    'cutoff' is typically an integer ID representing the minimum acceptable quality.
    """
    resp = lidarr_request("qualityprofile", "GET")
    if not resp or not isinstance(resp, list):
        logger.warning("Could not retrieve quality profiles or invalid format.")
        return {}
    profiles = {}
    for p in resp:
        prof_id = p.get("id")
        if prof_id is not None:
            profiles[prof_id] = p
    return profiles

def refresh_artist(artist_id: int) -> Optional[Dict]:
    """
    POST /api/v1/command
    { "name": "RefreshArtist", "artistIds": [ artist_id ] }
    """
    data = {
        "name": "RefreshArtist",
        "artistIds": [artist_id],
    }
    return lidarr_request("command", method="POST", data=data)

def missing_album_search(artist_id: int) -> Optional[Dict]:
    """
    POST /api/v1/command
    { "name": "MissingAlbumSearch", "artistIds": [ artist_id ] }
    """
    data = {
        "name": "MissingAlbumSearch",
        "artistIds": [artist_id],
    }
    return lidarr_request("command", method="POST", data=data)

def album_search(album_id: int) -> Optional[Dict]:
    """
    POST /api/v1/command
    { "name": "AlbumSearch", "albumIds": [ album_id ] }
    """
    data = {
        "name": "AlbumSearch",
        "albumIds": [album_id],
    }
    return lidarr_request("command", method="POST", data=data)

def track_search(track_id: int) -> Optional[Dict]:
    """
    POST /api/v1/command
    { "name": "TrackSearch", "trackIds": [ track_id ] }
    """
    data = {
        "name": "TrackSearch",
        "trackIds": [track_id],
    }
    return lidarr_request("command", method="POST", data=data)

# ---------------------------
# MISSING: ARTIST MODE
# ---------------------------
def process_artists_missing() -> None:
    logger.info("=== Running in ARTIST MODE (Missing) ===")
    artists = get_artists_json()
    if not artists:
        logger.error("ERROR: Unable to retrieve artist data. Retrying in 60s...")
        time.sleep(60)
        return

    if MONITORED_ONLY:
        logger.info("MONITORED_ONLY=true => only monitored artists with missing tracks.")
        incomplete_artists = [
            a for a in artists
            if a.get("monitored") is True
            and a.get("statistics", {}).get("trackCount", 0) > a.get("statistics", {}).get("trackFileCount", 0)
        ]
    else:
        logger.info("MONITORED_ONLY=false => all incomplete artists.")
        incomplete_artists = [
            a for a in artists
            if a.get("statistics", {}).get("trackCount", 0) > a.get("statistics", {}).get("trackFileCount", 0)
        ]

    if not incomplete_artists:
        logger.info("No incomplete artists found. Waiting 60s...")
        time.sleep(60)
        return

    logger.info(f"Found {len(incomplete_artists)} incomplete artist(s).")
    processed_count = 0
    used_indices = set()

    while True:
        if MAX_ITEMS > 0 and processed_count >= MAX_ITEMS:
            logger.info(f"Reached MAX_ITEMS ({MAX_ITEMS}). Exiting loop.")
            break
        if len(used_indices) >= len(incomplete_artists):
            logger.info("All incomplete artists processed. Exiting loop.")
            break

        if RANDOM_SELECTION and len(incomplete_artists) > 1:
            while True:
                idx = random.randint(0, len(incomplete_artists) - 1)
                if idx not in used_indices:
                    break
        else:
            idx_candidates = [i for i in range(len(incomplete_artists)) if i not in used_indices]
            if not idx_candidates:
                break
            idx = idx_candidates[0]

        used_indices.add(idx)
        artist = incomplete_artists[idx]
        artist_id = artist["id"]
        artist_name = artist.get("artistName", "Unknown Artist")
        track_count = artist.get("statistics", {}).get("trackCount", 0)
        track_file_count = artist.get("statistics", {}).get("trackFileCount", 0)
        missing = track_count - track_file_count

        logger.info(f"Processing artist: '{artist_name}' (ID={artist_id}), missing {missing} track(s).")

        # 1) Refresh artist
        refresh_resp = refresh_artist(artist_id)
        if not refresh_resp or "id" not in refresh_resp:
            logger.warning("WARNING: Could not refresh. Skipping this artist.")
            time.sleep(10)
            continue
        logger.info(f"Refresh command accepted (ID={refresh_resp['id']}). Sleeping 5s...")
        time.sleep(5)

        # 2) MissingAlbumSearch
        search_resp = missing_album_search(artist_id)
        if search_resp and "id" in search_resp:
            logger.info(f"MissingAlbumSearch accepted (ID={search_resp['id']}).")
        else:
            logger.warning("WARNING: MissingAlbumSearch failed. Trying fallback 'AlbumSearch' by artist...")
            fallback_data = {
                "name": "AlbumSearch",
                "artistIds": [artist_id],
            }
            fallback_resp = lidarr_request("command", method="POST", data=fallback_data)
            if fallback_resp and "id" in fallback_resp:
                logger.info(f"Fallback AlbumSearch accepted (ID={fallback_resp['id']}).")
            else:
                logger.warning("Fallback also failed. Skipping this artist.")

        processed_count += 1
        logger.info(f"Processed artist. Sleeping {SLEEP_DURATION}s...")
        time.sleep(SLEEP_DURATION)

# ---------------------------
# MISSING: ALBUM MODE
# ---------------------------
def process_albums_missing() -> None:
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

    while True:
        if MAX_ITEMS > 0 and processed_count >= MAX_ITEMS:
            logger.info("Reached MAX_ITEMS. Exiting loop.")
            break
        if len(used_indices) >= len(incomplete_albums):
            logger.info("All incomplete albums processed. Exiting loop.")
            break

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

# ---------------------------
# UPGRADE: Track-Level Logic
# ---------------------------
def track_needs_upgrade(track: Dict, profiles: Dict[int, Dict]) -> bool:
    """
    Determine if a track's current quality is below its profile's cutoff.
    This logic may need to be adapted to your Lidarr's actual JSON structure.
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

    while True:
        if MAX_ITEMS > 0 and processed_count >= MAX_ITEMS:
            logger.info(f"Reached MAX_ITEMS={MAX_ITEMS}. Stopping upgrade loop.")
            break
        if len(used_indices) >= len(upgrade_candidates):
            logger.info("All upgrade candidates processed.")
            break

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

# ---------------------------
# Main Loop
# ---------------------------
def main_loop() -> None:
    while True:
        logger.info(f"=== Starting Huntarr-Lidarr cycle (MODE={SEARCH_MODE}, TYPE={SEARCH_TYPE}) ===")

        # Only run missing search when SEARCH_TYPE is "missing" or "both"
        if SEARCH_TYPE in ["missing", "both"]:
            if SEARCH_MODE == "artist":
                process_artists_missing()
            elif SEARCH_MODE == "album":
                process_albums_missing()
            else:
                logger.warning(f"Unknown SEARCH_MODE={SEARCH_MODE}; defaulting to artist missing.")
                process_artists_missing()

        # Only run upgrade search when SEARCH_TYPE is "upgrade" or "both"
        if SEARCH_TYPE in ["upgrade", "both"]:
            process_cutoff_upgrades()

        logger.info("Cycle complete. Waiting 60s before next cycle...")
        time.sleep(60)


if __name__ == "__main__":
    logger.info("=== Huntarr [Lidarr Edition] Starting ===")
    logger.info(f"API URL: {API_URL}")
    logger.info(f"Configuration: MAX_ITEMS={MAX_ITEMS}, SLEEP_DURATION={SLEEP_DURATION}s")
    logger.info(f"MONITORED_ONLY={MONITORED_ONLY}, RANDOM_SELECTION={RANDOM_SELECTION}")
    logger.info(f"SEARCH_MODE={SEARCH_MODE}, SEARCH_TYPE={SEARCH_TYPE}")
    logger.debug(f"API_KEY={API_KEY}")

    try:
        main_loop()
    except KeyboardInterrupt:
        logger.info("Huntarr-Lidarr stopped by user.")
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        raise