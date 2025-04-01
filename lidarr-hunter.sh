#!/usr/bin/env bash

# ---------------------------
# Configuration
# ---------------------------
# Use environment variables if provided; otherwise, fall back to defaults.
API_KEY=${API_KEY:-"your-api-key"}
API_URL=${API_URL:-"http://your-lidarr-address:8686"}

# How many items (artists, albums, or songs) to process before restarting the search cycle
MAX_ITEMS=${MAX_ITEMS:-1}

# Sleep duration in seconds after processing an item (900=15min)
SLEEP_DURATION=${SLEEP_DURATION:-900}

# Set to true to pick items randomly, false to go in order
RANDOM_SELECTION=${RANDOM_SELECTION:-true}

# If MONITORED_ONLY is set to true, only process monitored artists/albums/tracks
MONITORED_ONLY=${MONITORED_ONLY:-false}

# Modes:
#   "artist" - process incomplete artists
#   "album"  - process incomplete albums individually
#   "song"   - process individual missing tracks
SEARCH_MODE=${SEARCH_MODE:-"artist"}

# ---------------------------
# Helper Functions
# ---------------------------
get_artists_json() {
  curl -s -H "X-Api-Key: $API_KEY" "$API_URL/api/v1/artist"
}

get_albums_for_artist() {
  local artist_id="$1"
  curl -s -H "X-Api-Key: $API_KEY" "$API_URL/api/v1/album?artistId=$artist_id"
}

get_tracks_for_album() {
  local album_id="$1"
  curl -s -H "X-Api-Key: $API_KEY" "$API_URL/api/v1/track?albumId=$album_id"
}

refresh_artist() {
  local artist_id="$1"
  curl -s -X POST \
    -H "X-Api-Key: $API_KEY" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"RefreshArtist\",\"artistIds\":[$artist_id]}" \
    "$API_URL/api/v1/command"
}

missing_album_search() {
  local artist_id="$1"
  curl -s -X POST \
    -H "X-Api-Key: $API_KEY" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"MissingAlbumSearch\",\"artistIds\":[$artist_id]}" \
    "$API_URL/api/v1/command"
}

album_search() {
  local album_id="$1"
  curl -s -X POST \
    -H "X-Api-Key: $API_KEY" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"AlbumSearch\",\"albumIds\":[$album_id]}" \
    "$API_URL/api/v1/command"
}

# ---------------------------
# ARTIST MODE
# ---------------------------
process_artists_mode() {
  echo "=== Running in ARTIST MODE ==="
  ARTISTS_JSON=$(get_artists_json)
  if [ -z "$ARTISTS_JSON" ]; then
    echo "ERROR: Unable to retrieve artist data. Retrying in 60s..."
    sleep 60
    return
  fi

  # Filter incomplete artists (trackCount > trackFileCount)
  if [ "$MONITORED_ONLY" = "true" ]; then
    echo "MONITORED_ONLY=true => Only monitored artists."
    INCOMPLETE_ARTISTS_JSON=$(echo "$ARTISTS_JSON" | \
      jq '[.[] | select(.monitored == true and .statistics.trackCount > .statistics.trackFileCount)]')
  else
    echo "MONITORED_ONLY=false => All artists with missing tracks."
    INCOMPLETE_ARTISTS_JSON=$(echo "$ARTISTS_JSON" | \
      jq '[.[] | select(.statistics.trackCount > .statistics.trackFileCount)]')
  fi

  TOTAL_INCOMPLETE=$(echo "$INCOMPLETE_ARTISTS_JSON" | jq 'length')
  if [ "$TOTAL_INCOMPLETE" -eq 0 ]; then
    echo "No incomplete artists. Waiting 60s..."
    sleep 60
    return
  fi

  echo "Found $TOTAL_INCOMPLETE incomplete artist(s)."
  ARTISTS_PROCESSED=0
  ALREADY_CHECKED=()

  while true; do
    if [ "$MAX_ITEMS" -gt 0 ] && [ "$ARTISTS_PROCESSED" -ge "$MAX_ITEMS" ]; then
      echo "Reached MAX_ITEMS ($MAX_ITEMS). Exiting loop."
      break
    fi
    if [ ${#ALREADY_CHECKED[@]} -ge "$TOTAL_INCOMPLETE" ]; then
      echo "All incomplete artists processed. Exiting loop."
      break
    fi

    # Pick an index
    if [ "$RANDOM_SELECTION" = "true" ] && [ "$TOTAL_INCOMPLETE" -gt 1 ]; then
      while true; do
        INDEX=$((RANDOM % TOTAL_INCOMPLETE))
        if [[ ! " ${ALREADY_CHECKED[*]} " =~ " $INDEX " ]]; then
          break
        fi
      done
    else
      for ((i=0; i<TOTAL_INCOMPLETE; i++)); do
        if [[ ! " ${ALREADY_CHECKED[*]} " =~ " $i " ]]; then
          INDEX=$i
          break
        fi
      done
    fi

    ALREADY_CHECKED+=("$INDEX")

    ARTIST=$(echo "$INCOMPLETE_ARTISTS_JSON" | jq ".[$INDEX]")
    ARTIST_ID=$(echo "$ARTIST" | jq '.id')
    ARTIST_NAME=$(echo "$ARTIST" | jq -r '.artistName')
    TRACK_COUNT=$(echo "$ARTIST" | jq '.statistics.trackCount')
    TRACK_FILE_COUNT=$(echo "$ARTIST" | jq '.statistics.trackFileCount')
    MISSING=$((TRACK_COUNT - TRACK_FILE_COUNT))

    echo "Processing artist: \"$ARTIST_NAME\" (ID: $ARTIST_ID) with $MISSING missing track(s)."

    # Refresh artist
    REFRESH_RESP=$(refresh_artist "$ARTIST_ID")
    REFRESH_ID=$(echo "$REFRESH_RESP" | jq '.id // empty')
    if [ -z "$REFRESH_ID" ]; then
      echo "WARNING: Could not refresh. Skipping this artist."
      sleep 10
      continue
    fi

    echo "Refresh command accepted (ID: $REFRESH_ID). Sleeping 5s..."
    sleep 5

    # MissingAlbumSearch
    SEARCH_RESP=$(missing_album_search "$ARTIST_ID")
    SEARCH_ID=$(echo "$SEARCH_RESP" | jq '.id // empty')
    if [ -n "$SEARCH_ID" ]; then
      echo "MissingAlbumSearch accepted (ID: $SEARCH_ID)."
    else
      echo "WARNING: MissingAlbumSearch failed. Trying fallback 'AlbumSearch'..."
      FALLBACK_SEARCH=$(curl -s -X POST \
        -H "X-Api-Key: $API_KEY" \
        -H "Content-Type: application/json" \
        -d "{\"name\":\"AlbumSearch\",\"artistIds\":[$ARTIST_ID]}" \
        "$API_URL/api/v1/command")
      FALLBACK_ID=$(echo "$FALLBACK_SEARCH" | jq '.id // empty')
      [ -n "$FALLBACK_ID" ] && echo "Fallback AlbumSearch accepted (ID: $FALLBACK_ID)."
    fi

    ARTISTS_PROCESSED=$((ARTISTS_PROCESSED + 1))
    echo "Processed artist. Sleeping $SLEEP_DURATION..."
    sleep "$SLEEP_DURATION"
  done
}

# ---------------------------
# ALBUM MODE
# ---------------------------
process_albums_mode() {
  echo "=== Running in ALBUM MODE ==="
  ARTISTS_JSON=$(get_artists_json)
  [ -z "$ARTISTS_JSON" ] && { echo "ERROR: No artist data. 60s wait..."; sleep 60; return; }

  # We'll gather all incomplete albums from all artists
  INCOMPLETE_ALBUMS=()

  # Loop through each artist
  MAPFILE_ARTISTS=$(echo "$ARTISTS_JSON" | jq -c '.[]')
  while read -r ARTIST; do
    [ -z "$ARTIST" ] && continue

    local_id=$(echo "$ARTIST" | jq '.id')
    local_name=$(echo "$ARTIST" | jq -r '.artistName')
    local_monitored=$(echo "$ARTIST" | jq -r '.monitored')

    # If MONITORED_ONLY, skip unmonitored artists
    if [ "$MONITORED_ONLY" = "true" ] && [ "$local_monitored" != "true" ]; then
      continue
    fi

    # Get albums for this artist
    ALBUMS_JSON=$(get_albums_for_artist "$local_id")
    [ -z "$ALBUMS_JSON" ] && continue

    MAPFILE_ALBUMS=$(echo "$ALBUMS_JSON" | jq -c '.[]')
    while read -r ALBUM; do
      [ -z "$ALBUM" ] && continue

      album_id=$(echo "$ALBUM" | jq '.id')
      album_title=$(echo "$ALBUM" | jq -r '.title')
      album_monitored=$(echo "$ALBUM" | jq -r '.monitored')
      album_track_count=$(echo "$ALBUM" | jq '.statistics.trackCount')
      album_file_count=$(echo "$ALBUM" | jq '.statistics.trackFileCount')

      if [ "$MONITORED_ONLY" = "true" ] && [ "$album_monitored" != "true" ]; then
        continue
      fi

      # If this album is missing tracks
      if [ $((album_track_count - album_file_count)) -gt 0 ]; then
        INCOMPLETE_ALBUMS+=("{\"artistId\":$local_id,\"artistName\":\"$local_name\",\"albumId\":$album_id,\"albumTitle\":\"$album_title\"}")
      fi
    done <<< "$MAPFILE_ALBUMS"
  done <<< "$MAPFILE_ARTISTS"

  TOTAL_ALBUMS=${#INCOMPLETE_ALBUMS[@]}
  if [ "$TOTAL_ALBUMS" -eq 0 ]; then
    echo "No incomplete albums found. 60s wait..."
    sleep 60
    return
  fi

  echo "Found $TOTAL_ALBUMS incomplete album(s)."
  ALBUMS_PROCESSED=0
  ALREADY_CHECKED=()

  while true; do
    if [ "$MAX_ITEMS" -gt 0 ] && [ "$ALBUMS_PROCESSED" -ge "$MAX_ITEMS" ]; then
      echo "Reached MAX_ITEMS. Exiting loop."
      break
    fi

    if [ ${#ALREADY_CHECKED[@]} -ge "$TOTAL_ALBUMS" ]; then
      echo "All incomplete albums processed. Exiting loop."
      break
    fi

    # Pick index
    if [ "$RANDOM_SELECTION" = "true" ] && [ "$TOTAL_ALBUMS" -gt 1 ]; then
      while true; do
        INDEX=$((RANDOM % TOTAL_ALBUMS))
        if [[ ! " ${ALREADY_CHECKED[*]} " =~ " $INDEX " ]]; then
          break
        fi
      done
    else
      for ((i=0; i<TOTAL_ALBUMS; i++)); do
        if [[ ! " ${ALREADY_CHECKED[*]} " =~ " $i " ]]; then
          INDEX=$i
          break
        fi
      done
    fi

    ALREADY_CHECKED+=("$INDEX")

    ALBUM_OBJ="${INCOMPLETE_ALBUMS[$INDEX]}"
    ARTIST_ID=$(echo "$ALBUM_OBJ" | jq '.artistId')
    ARTIST_NAME=$(echo "$ALBUM_OBJ" | jq -r '.artistName')
    ALBUM_ID=$(echo "$ALBUM_OBJ" | jq '.albumId')
    ALBUM_TITLE=$(echo "$ALBUM_OBJ" | jq -r '.albumTitle')

    echo "Processing incomplete album \"$ALBUM_TITLE\" by \"$ARTIST_NAME\"..."

    # 1) Refresh the artist (Lidarr lacks a direct "RefreshAlbum" command)
    REFRESH_RESP=$(refresh_artist "$ARTIST_ID")
    REFRESH_ID=$(echo "$REFRESH_RESP" | jq '.id // empty')
    if [ -z "$REFRESH_ID" ]; then
      echo "WARNING: Could not refresh artist $ARTIST_NAME. Skipping album."
      sleep 10
      continue
    fi
    echo "Refresh command accepted (ID: $REFRESH_ID). Waiting 5s..."
    sleep 5

    # 2) AlbumSearch
    SEARCH_RESP=$(album_search "$ALBUM_ID")
    SEARCH_ID=$(echo "$SEARCH_RESP" | jq '.id // empty')
    if [ -n "$SEARCH_ID" ]; then
      echo "AlbumSearch command accepted (ID: $SEARCH_ID)."
    else
      echo "WARNING: AlbumSearch command failed for album $ALBUM_TITLE."
    fi

    ALBUMS_PROCESSED=$((ALBUMS_PROCESSED + 1))
    echo "Album processed. Sleeping $SLEEP_DURATION..."
    sleep "$SLEEP_DURATION"
  done
}

# ---------------------------
# SONG MODE
# ---------------------------
process_songs_mode() {
  echo "=== Running in SONG MODE ==="

  ARTISTS_JSON=$(get_artists_json)
  if [ -z "$ARTISTS_JSON" ]; then
    echo "ERROR: No artist data. 60s wait..."
    sleep 60
    return
  fi

  MISSING_TRACKS=()

  # Gather all missing tracks
  MAPFILE_ARTISTS=$(echo "$ARTISTS_JSON" | jq -c '.[]')
  while read -r ARTIST; do
    [ -z "$ARTIST" ] && continue
    ARTIST_ID=$(echo "$ARTIST" | jq '.id')
    ARTIST_NAME=$(echo "$ARTIST" | jq -r '.artistName')
    ARTIST_MONITORED=$(echo "$ARTIST" | jq -r '.monitored')
    TRACK_COUNT=$(echo "$ARTIST" | jq '.statistics.trackCount')
    TRACK_FILE_COUNT=$(echo "$ARTIST" | jq '.statistics.trackFileCount')

    if [ "$MONITORED_ONLY" = "true" ] && [ "$ARTIST_MONITORED" != "true" ]; then
      continue
    fi

    if [ $((TRACK_COUNT - TRACK_FILE_COUNT)) -le 0 ]; then
      continue
    fi

    # Collect albums
    ALBUMS_JSON=$(get_albums_for_artist "$ARTIST_ID")
    [ -z "$ALBUMS_JSON" ] && continue

    MAPFILE_ALBUMS=$(echo "$ALBUMS_JSON" | jq -c '.[]')
    while read -r ALBUM; do
      [ -z "$ALBUM" ] && continue
      ALBUM_ID=$(echo "$ALBUM" | jq '.id')
      ALBUM_TITLE=$(echo "$ALBUM" | jq -r '.title')
      ALBUM_MONITORED=$(echo "$ALBUM" | jq -r '.monitored')

      if [ "$MONITORED_ONLY" = "true" ] && [ "$ALBUM_MONITORED" != "true" ]; then
        continue
      fi

      TRACKS_JSON=$(get_tracks_for_album "$ALBUM_ID")
      [ -z "$TRACKS_JSON" ] && continue

      MAPFILE_TRACKS=$(echo "$TRACKS_JSON" | jq -c '.[]')
      while read -r TRACK; do
        [ -z "$TRACK" ] && continue
        HAS_FILE=$(echo "$TRACK" | jq -r '.hasFile')
        TRACK_MONITORED=$(echo "$TRACK" | jq -r '.monitored')
        TRACK_ID=$(echo "$TRACK" | jq '.id')
        TRACK_TITLE=$(echo "$TRACK" | jq -r '.title')

        if [ "$HAS_FILE" = "false" ]; then
          if [ "$MONITORED_ONLY" = "true" ] && [ "$TRACK_MONITORED" != "true" ]; then
            continue
          fi
          MISSING_TRACKS+=("{\"artistId\":$ARTIST_ID,\"artistName\":\"$ARTIST_NAME\",\"albumId\":$ALBUM_ID,\"albumTitle\":\"$ALBUM_TITLE\",\"trackId\":$TRACK_ID,\"trackTitle\":\"$TRACK_TITLE\"}")
        fi
      done <<< "$MAPFILE_TRACKS"
    done <<< "$MAPFILE_ALBUMS"
  done <<< "$MAPFILE_ARTISTS"

  TOTAL_MISSING=${#MISSING_TRACKS[@]}
  if [ "$TOTAL_MISSING" -eq 0 ]; then
    echo "No missing tracks in SONG MODE. 60s wait..."
    sleep 60
    return
  fi

  echo "Found $TOTAL_MISSING missing track(s)."
  TRACKS_PROCESSED=0
  ALREADY_CHECKED=()

  while true; do
    if [ "$MAX_ITEMS" -gt 0 ] && [ "$TRACKS_PROCESSED" -ge "$MAX_ITEMS" ]; then
      echo "Reached MAX_ITEMS. Exiting loop."
      break
    fi
    if [ ${#ALREADY_CHECKED[@]} -ge "$TOTAL_MISSING" ]; then
      echo "All missing tracks processed. Exiting loop."
      break
    fi

    # pick index
    if [ "$RANDOM_SELECTION" = "true" ] && [ "$TOTAL_MISSING" -gt 1 ]; then
      while true; do
        INDEX=$((RANDOM % TOTAL_MISSING))
        if [[ ! " ${ALREADY_CHECKED[*]} " =~ " $INDEX " ]]; then
          break
        fi
      done
    else
      for ((i=0; i<TOTAL_MISSING; i++)); do
        if [[ ! " ${ALREADY_CHECKED[*]} " =~ " $i " ]]; then
          INDEX=$i
          break
        fi
      done
    fi

    ALREADY_CHECKED+=("$INDEX")

    TRACK_OBJ="${MISSING_TRACKS[$INDEX]}"
    ARTIST_ID=$(echo "$TRACK_OBJ" | jq '.artistId')
    ARTIST_NAME=$(echo "$TRACK_OBJ" | jq -r '.artistName')
    ALBUM_ID=$(echo "$TRACK_OBJ" | jq '.albumId')
    ALBUM_TITLE=$(echo "$TRACK_OBJ" | jq -r '.albumTitle')
    TRACK_ID=$(echo "$TRACK_OBJ" | jq '.trackId')
    TRACK_TITLE=$(echo "$TRACK_OBJ" | jq -r '.trackTitle')

    echo "Processing missing track \"$TRACK_TITLE\" from \"$ALBUM_TITLE\" by \"$ARTIST_NAME\"..."

    # Refresh artist
    REFRESH_RESP=$(refresh_artist "$ARTIST_ID")
    REFRESH_ID=$(echo "$REFRESH_RESP" | jq '.id // empty')
    if [ -z "$REFRESH_ID" ]; then
      echo "WARNING: Could not refresh. Skipping track."
      sleep 10
      continue
    fi
    echo "Refresh command accepted (ID: $REFRESH_ID). Waiting 5s..."
    sleep 5

    # AlbumSearch on the track's album
    SEARCH_RESP=$(album_search "$ALBUM_ID")
    SEARCH_ID=$(echo "$SEARCH_RESP" | jq '.id // empty')
    if [ -n "$SEARCH_ID" ]; then
      echo "AlbumSearch accepted (ID: $SEARCH_ID)."
    else
      echo "WARNING: AlbumSearch failed for album $ALBUM_TITLE."
    fi

    TRACKS_PROCESSED=$((TRACKS_PROCESSED + 1))
    echo "Track processed. Sleeping $SLEEP_DURATION..."
    sleep "$SLEEP_DURATION"
  done
}

# ---------------------------
# Main Loop
# ---------------------------
while true; do
  case "$SEARCH_MODE" in
    "song")
      process_songs_mode
      ;;
    "album")
      process_albums_mode
      ;;
    *)
      process_artists_mode
      ;;
  esac

  echo "Cycle complete. Waiting 60s before next cycle..."
  sleep 60
done
