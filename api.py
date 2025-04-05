#!/usr/bin/env python3
"""
Lidarr API Helper Functions
Handles all communication with the Lidarr API
"""

import requests
from typing import List, Dict, Any, Optional
from utils.logger import logger
from config import API_KEY, API_URL

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
    """Retrieve all artists from Lidarr"""
    return lidarr_request("artist", "GET")

def get_albums_for_artist(artist_id: int) -> Optional[List[Dict]]:
    """Retrieve all albums for a specific artist"""
    return lidarr_request(f"album?artistId={artist_id}", "GET")

def get_tracks_for_album(album_id: int) -> Optional[List[Dict]]:
    """Retrieve all tracks for a specific album"""
    return lidarr_request(f"track?albumId={album_id}", "GET")

def get_quality_profiles() -> Dict[int, Dict]:
    """
    Returns a dict mapping profile IDs to their details
    
    Returns:
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
    """Refresh metadata for an artist"""
    data = {
        "name": "RefreshArtist",
        "artistIds": [artist_id],
    }
    return lidarr_request("command", method="POST", data=data)

def missing_album_search(artist_id: int) -> Optional[Dict]:
    """Search for missing albums for an artist"""
    data = {
        "name": "MissingAlbumSearch",
        "artistIds": [artist_id],
    }
    return lidarr_request("command", method="POST", data=data)

def album_search(album_id: int) -> Optional[Dict]:
    """Search for a specific album"""
    data = {
        "name": "AlbumSearch",
        "albumIds": [album_id],
    }
    return lidarr_request("command", method="POST", data=data)

def track_search(track_id: int) -> Optional[Dict]:
    """Search for a specific track"""
    data = {
        "name": "TrackSearch",
        "trackIds": [track_id],
    }
    return lidarr_request("command", method="POST", data=data)