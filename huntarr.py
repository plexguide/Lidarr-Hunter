#!/usr/bin/env python3
"""
Huntarr [Lidarr Edition] - Python Version
Automatically search for missing or upgrade items (Artists, Albums, or Songs) in Lidarr.
"""

import os
import time
import json
import random
import logging
import requests

from typing import List, Dict, Any, Optional

# ---------------------------
# Environment Variables / Configuration
# ---------------------------

API_KEY = os.environ.get("API_KEY", "your-api-key")
API_URL = os.environ.get("API_URL", "http://your-lidarr-address:8686")

# How many items (artists, albums, or songs) to process per cycle
try:
    MAX_ITEMS = int(os.environ.get("MAX_ITEMS", "1"))
except ValueError:
    MAX_ITEMS = 1
    print(f"[WARN] Invalid MAX_ITEMS value; using default {MAX_ITEMS}")

# Sleep duration in seconds after processing each item (default 900 = 15 minutes)
try:
    SLEEP_DURATION = int(os.environ.get("SLEEP_DURATION", "900"))
except ValueError:
    SLEEP_DURATION = 900
    print(f"[WARN] Invalid SLEEP_DURATION value; using default {SLEEP_DURATION}")

# If True, pick items randomly; if False, go in order
RANDOM_SELECTION = os.environ.get("RANDOM_SELECTION", "true").lower() == "true"

# If MONITORED_ONLY=true, only process monitored artists/albums/songs
MONITORED_ONLY = os.environ.get("MONITORED_ONLY", "true").lower() == "true"

# SEARCH_MODE: "artist", "album", or "song"
SEARCH_MODE = os.environ.get("SEARCH_MODE", "artist")

# SEARCH_TYPE is new: "missing", "upgrade", or "both"
# - "missing" => same logic as your old bash script
# - "upgrade" => attempt to find cutoff-unmet (song) tracks
# - "both"    => do missing first, then upgrade
SEARCH_TYPE = os.environ.get("SEARCH_TYPE", "missing")

# Enable debug logging
DEBUG_MODE = os.environ.get("DEBUG_MODE", "false").lower() == "true"

# Set up Python logging
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
    Example endpoint: "artist", "album", "track", "command", or "wanted".
    """
    url = f"{API_URL}/api/v1/{endpoint}"
    headers = {
        "X-Api-Key": API_KEY,
        "Content-Type": "application/json",
    }

    try:
        if method.upper() == "GET":
            response = requests.get(url, headers=headers, timeout=30)
        elif method.upper() == "POST":
            response = requests.post(url, headers=headers, json=data, timeout=30)
        else:
            logger.error(f"Unsupported HTTP method: {method}")
            return None

        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"API request error to {url}: {e}")
        return None

def get_artists_json() -> Optional[List[Dict]]:
    return lidarr_request("artist", "GET")

def get_albums_for_artist(artist_id: int) -> Optional[List[Dict]]:
    return lidarr_request(f"album?artistId={artist_id}", "GET")

def get_tracks_for_album(album_id: int) -> Optional[List[Dict]]:
    return lidarr_request(f"track?albumId={album_id}", "GET")

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

    # Filter incomplete artists (trackCount > trackFileCount)
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
            # sequential pick
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

        # Skip unmonitored artists if MONITORED_ONLY
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
# MISSING: SONG MODE
# ---------------------------
def process_songs_missing() -> None:
    logger.info("=== Running in SONG MODE (Missing) ===")

    artists = get_artists_json()
    if not artists:
        logger.error("ERROR: No artist data. 60s wait...")
        time.sleep(60)
        return

    missing_tracks = []
    # Gather all missing tracks
    for artist in artists:
        artist_id = artist["id"]
        artist_name = artist.get("artistName", "Unknown Artist")
        artist_monitored = artist.get("monitored", False)
        track_count = artist.get("statistics", {}).get("trackCount", 0)
        track_file_count = artist.get("statistics", {}).get("trackFileCount", 0)

        if MONITORED_ONLY and not artist_monitored:
            continue
        if track_count <= track_file_count:
            continue

        albums = get_albums_for_artist(artist_id) or []
        for alb in albums:
            album_id = alb["id"]
            album_title = alb.get("title", "Unknown Album")
            album_monitored = alb.get("monitored", False)

            if MONITORED_ONLY and not album_monitored:
                continue

            tracks = get_tracks_for_album(album_id) or []
            for t in tracks:
                has_file = t.get("hasFile", False)
                track_monitored = t.get("monitored", False)
                track_id = t["id"]
                track_title = t.get("title", "Unknown Track")

                if not has_file:
                    if MONITORED_ONLY and not track_monitored:
                        continue
                    missing_tracks.append({
                        "artistId": artist_id,
                        "artistName": artist_name,
                        "albumId": album_id,
                        "albumTitle": album_title,
                        "trackId": track_id,
                        "trackTitle": track_title
                    })

    if not missing_tracks:
        logger.info("No missing tracks in SONG MODE. 60s wait...")
        time.sleep(60)
        return

    logger.info(f"Found {len(missing_tracks)} missing track(s).")
    processed_count = 0
    used_indices = set()

    while True:
        if MAX_ITEMS > 0 and processed_count >= MAX_ITEMS:
            logger.info("Reached MAX_ITEMS. Exiting loop.")
            break
        if len(used_indices) >= len(missing_tracks):
            logger.info("All missing tracks processed. Exiting loop.")
            break

        if RANDOM_SELECTION and len(missing_tracks) > 1:
            while True:
                idx = random.randint(0, len(missing_tracks) - 1)
                if idx not in used_indices:
                    break
        else:
            idx_candidates = [i for i in range(len(missing_tracks)) if i not in used_indices]
            if not idx_candidates:
                break
            idx = idx_candidates[0]

        used_indices.add(idx)
        track_obj = missing_tracks[idx]
        artist_id = track_obj["artistId"]
        artist_name = track_obj["artistName"]
        album_id = track_obj["albumId"]
        album_title = track_obj["albumTitle"]
        track_id = track_obj["trackId"]
        track_title = track_obj["trackTitle"]

        logger.info(f"Processing missing track '{track_title}' from album '{album_title}' by '{artist_name}'...")

        # Refresh artist
        refresh_resp = refresh_artist(artist_id)
        if not refresh_resp or "id" not in refresh_resp:
            logger.warning("WARNING: Could not refresh. Skipping track.")
            time.sleep(10)
            continue
        logger.info(f"Refresh command accepted (ID={refresh_resp['id']}). Waiting 5s...")
        time.sleep(5)

        # AlbumSearch on the track's album
        search_resp = album_search(album_id)
        if search_resp and "id" in search_resp:
            logger.info(f"AlbumSearch accepted (ID={search_resp['id']}).")
        else:
            logger.warning(f"WARNING: AlbumSearch failed for album '{album_title}'.")

        processed_count += 1
        logger.info(f"Track processed. Sleeping {SLEEP_DURATION}s...")
        time.sleep(SLEEP_DURATION)

# ---------------------------
# UPGRADE: SONG MODE
# ---------------------------
def process_songs_upgrade() -> None:
    """
    Attempts to find songs that do not meet quality cutoff (cutoffNotMet) and re-search them.
    Uses the GET /api/v1/wanted?filterKey=cutoffNotMet approach if Lidarr supports it.
    """
    logger.info("=== Running in SONG MODE (Upgrade) ===")

    # We'll pull "cutoffNotMet" items from /api/v1/wanted
    # Example: GET /api/v1/wanted?filterKey=cutoffNotMet&page=1&pageSize=50
    # The response typically has { "records": [...], "totalRecords": <num> }
    # We'll do a simple single-page approach or a loop if you want multiple pages.

    page = 1
    processed_count = 0

    while True:
        if MAX_ITEMS > 0 and processed_count >= MAX_ITEMS:
            logger.info(f"Reached MAX_ITEMS={MAX_ITEMS}. Stopping upgrade loop.")
            break

        logger.info(f"Fetching upgrade-needed songs from wanted?filterKey=cutoffNotMet (page={page})...")
        resp = lidarr_request(f"wanted?filterKey=cutoffNotMet&page={page}&pageSize=50", "GET")
        if not resp or "records" not in resp:
            logger.info("No 'cutoffNotMet' records found or invalid response. Stopping.")
            break

        records = resp["records"]
        total_records = resp.get("totalRecords", 0)
        logger.info(f"Found {len(records)} record(s) on page {page} out of {total_records} total unmet-quality songs.")

        if not records:
            # No more items to process
            break

        # In random mode, shuffle the list of records
        indices = list(range(len(records)))
        if RANDOM_SELECTION:
            random.shuffle(indices)

        for i in indices:
            if MAX_ITEMS > 0 and processed_count >= MAX_ITEMS:
                break

            track_obj = records[i]
            # The "wanted" record typically includes trackId, album, artist info
            # We have to confirm the data structure from Lidarr's "wanted" response.
            # Typically "trackFileId" or "id", let's check "id" is the track id or the record id.
            track_id = track_obj.get("id")
            hasFile = track_obj.get("hasFile", False)
            # We also expect track_obj to have "artist" or "artistId", "album" or "albumId".
            # In some versions, it might store them nested under trackObj["artist"]["id"]
            # or trackObj["album"]["id"].

            # Attempt to get album, artist, etc.
            artist_info = track_obj.get("artist") or {}
            artist_id = artist_info.get("id")
            artist_name = artist_info.get("artistName", "Unknown Artist")

            album_info = track_obj.get("album") or {}
            album_id = album_info.get("id")
            album_title = album_info.get("title", "Unknown Album")

            track_title = track_obj.get("title", "Unknown Track")

            # If MONITORED_ONLY, verify the track is monitored
            if MONITORED_ONLY:
                if not track_obj.get("monitored", True):
                    logger.info("Skipping unmonitored track.")
                    continue
                # Also skip if the artist or album is unmonitored (if the info is present).
                if "artist" in track_obj and track_obj["artist"].get("monitored", True) is False:
                    logger.info("Skipping track because artist is unmonitored.")
                    continue
                if "album" in track_obj and track_obj["album"].get("monitored", True) is False:
                    logger.info("Skipping track because album is unmonitored.")
                    continue

            logger.info(f"Upgrading track '{track_title}' (ID={track_id}) from album '{album_title}' by '{artist_name}'...")

            # 1) Refresh Artist
            if artist_id:
                refresh_resp = refresh_artist(artist_id)
                if not refresh_resp or "id" not in refresh_resp:
                    logger.warning("WARNING: Refresh command failed. Skipping this track.")
                    time.sleep(10)
                    continue
                logger.info(f"Refresh command accepted (ID={refresh_resp['id']}). Waiting 5s...")
                time.sleep(5)

            # 2) TrackSearch to force an upgrade
            if track_id:
                search_resp = track_search(track_id)
                if search_resp and "id" in search_resp:
                    logger.info(f"TrackSearch command accepted (ID={search_resp['id']}).")
                    processed_count += 1
                    logger.info(f"Processed {processed_count}/{MAX_ITEMS} upgrade songs this cycle.")
                else:
                    logger.warning(f"WARNING: TrackSearch command failed for track ID={track_id}.")
                    time.sleep(10)
            else:
                logger.warning("No valid track_id in the record. Skipping.")

            # Sleep after each item
            logger.info(f"Sleeping {SLEEP_DURATION}s...")
            time.sleep(SLEEP_DURATION)

        # If we got fewer records than pageSize or no new items, we can break
        if len(records) < 50:
            logger.info("No more pages to fetch or end of data.")
            break

        page += 1

    logger.info(f"Completed processing {processed_count} upgrade songs total in this run.")

# ---------------------------
# Main Loop
# ---------------------------
def main_loop() -> None:
    while True:
        logger.info(f"=== Starting Huntarr-Lidarr cycle (MODE={SEARCH_MODE}, TYPE={SEARCH_TYPE}) ===")

        # 1) If we are in "artist" or "album" mode, we only do "missing" logic (like original script).
        if SEARCH_MODE == "artist":
            process_artists_missing()

        elif SEARCH_MODE == "album":
            process_albums_missing()

        elif SEARCH_MODE == "song":
            # Now we have "missing", "upgrade", or "both"
            if SEARCH_TYPE == "missing":
                process_songs_missing()
            elif SEARCH_TYPE == "upgrade":
                process_songs_upgrade()
            elif SEARCH_TYPE == "both":
                process_songs_missing()
                process_songs_upgrade()
            else:
                logger.warning(f"Unknown SEARCH_TYPE={SEARCH_TYPE}. Using 'missing' as fallback.")
                process_songs_missing()
        else:
            logger.warning(f"Unknown SEARCH_MODE={SEARCH_MODE}. Defaulting to 'artist' missing logic.")
            process_artists_missing()

        logger.info("Cycle complete. Waiting 60s before next cycle...")
        time.sleep(60)

# ---------------------------
# Entry Point
# ---------------------------
if __name__ == "__main__":
    logger.info("=== Huntarr [Lidarr Edition] Starting ===")
    logger.info(f"API URL: {API_URL}")
    logger.info(f"Configuration: MAX_ITEMS={MAX_ITEMS}, SLEEP_DURATION={SLEEP_DURATION}s")
    logger.info(f"MONITORED_ONLY={MONITORED_ONLY}, RANDOM_SELECTION={RANDOM_SELECTION}")
    logger.info(f"SEARCH_MODE={SEARCH_MODE}, SEARCH_TYPE={SEARCH_TYPE}")
    logger.debug(f"API_KEY={API_KEY}")  # Be careful printing secrets in production

    try:
        main_loop()
    except KeyboardInterrupt:
        logger.info("Huntarr-Lidarr stopped by user.")
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        raise
