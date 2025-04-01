# Lidarr Hunter - Force Lidarr to Hunt Missing Songs

<h2 align="center">Want to Help? Click the Star in the Upper-Right Corner! ⭐</h2>

![image](https://github.com/user-attachments/assets/32ea6ab1-cf6d-43f2-b2aa-5953ef3bab01)

**NOTE**: This utilizes Lidarr API Version - `1`. The Script: [lidarr-hunter.sh](lidarr-hunter.sh)

## Table of Contents
- [Overview](#overview)
- [Related Projects](#related-projects)
- [Features](#features)
- [How It Works](#how-it-works)
- [Configuration Options](#configuration-options)
- [Installation Methods](#installation-methods)
  - [Docker Run](#docker-run)
  - [Docker Compose](#docker-compose)
  - [Unraid Users](#unraid-users)
  - [SystemD Service](#systemd-service)
- [Use Cases](#use-cases)
- [Tips](#tips)
- [Troubleshooting](#troubleshooting)

## Overview

This script continually searches your Lidarr library specifically for artists and albums that are missing (monitored but not downloaded) and automatically triggers searches for that missing music. It's designed to run continuously while being gentle on your indexers, helping you gradually complete your music collection.

## Related Projects

* [Sonarr Hunter](https://github.com/plexguide/Sonarr-Hunter) - Sister version for TV shows
* [Radarr Hunter](https://github.com/plexguide/Radarr-Hunter) - Sister version for movies
* [Unraid Intel ARC Deployment](https://github.com/plexguide/Unraid_Intel-ARC_Deployment) - Convert videos to AV1 Format (I've saved 325TB encoding to AV1)
* Visit [PlexGuide](https://plexguide.com) for more great scripts

## Features

- 🔄 **Continuous Operation**: Runs indefinitely until manually stopped
- 🎯 **Direct Missing Music Targeting**: Directly identifies and processes only missing albums and tracks
- 🎲 **Random Selection**: By default, selects missing music randomly to distribute searches across your library
- ⏱️ **Throttled Searches**: Includes configurable delays to prevent overloading indexers
- 📊 **Status Reporting**: Provides clear feedback about what it's doing and which music it's searching for
- 🛡️ **Error Handling**: Gracefully handles connection issues and API failures

## How It Works

1. **Initialization**: Connects to your Lidarr instance and retrieves a list of items based on your selected `SEARCH_MODE`
2. **Selection Process**: Randomly (or sequentially) selects an item from the filtered list
3. **Processing**: Based on your `SEARCH_MODE`:
   - **Artist Mode**: Searches for all missing music by a selected artist
   - **Album Mode**: Searches for individual missing albums
   - **Song Mode**: Searches for individual missing tracks
4. **Refresh**: Refreshes the metadata for the selected item
5. **Search Trigger**: Initiates the appropriate search command in Lidarr
6. **Throttling**: After processing an item, it pauses for the configured sleep duration
7. **Cycling**: After processing the configured number of items, it starts a new cycle

## Configuration Options

The following environment variables can be configured:

| Variable | Description | Default |
|----------|-------------|---------|
| `API_KEY` | Your Lidarr API key | Required |
| `API_URL` | URL to your Lidarr instance | Required |
| `MAX_ITEMS` | Number of items to process before restarting cycle | 1 |
| `SLEEP_DURATION` | Seconds to wait after processing an item (900=15min) | 900 |
| `RANDOM_SELECTION` | Use random selection (`true`) or sequential (`false`) | true |
| `MONITORED_ONLY` | Only process monitored artists/albums/tracks | false |
| `SEARCH_MODE` | Processing mode: "artist", "album", or "song" | "artist" |

**Search Modes Explained:**
- `artist`: Process incomplete artists (searches for all missing music by artist)
- `album`: Process incomplete albums individually (album-by-album search)
- `song`: Process individual missing tracks (song-by-song search)

## Installation Methods

### Docker Run

The simplest way to run Lidarr Hunter is via Docker:

```bash
docker run -d --name lidarr-hunter \
  --restart always \
  -e API_KEY="your-api-key" \
  -e API_URL="http://your-lidarr-address:8686" \
  -e MAX_ITEMS="1" \
  -e SLEEP_DURATION="900" \
  -e RANDOM_SELECTION="true" \
  -e MONITORED_ONLY="false" \
  -e SEARCH_MODE="artist" \
  admin9705/lidarr-hunter
```

### Docker Compose

For those who prefer Docker Compose, add this to your `docker-compose.yml` file:

```yaml
version: '3'
services:
  lidarr-hunter:
    container_name: lidarr-hunter
    image: admin9705/lidarr-hunter
    restart: always
    environment:
      - API_KEY=your-api-key
      - API_URL=http://lidarr:8686
      - MAX_ITEMS=1
      - SLEEP_DURATION=900
      - RANDOM_SELECTION=true
      - MONITORED_ONLY=false
      - SEARCH_MODE=artist
    networks:
      - your-network-name

networks:
  your-network-name:
    external: true
```

Then run:

```bash
docker-compose up -d lidarr-hunter
```

### Unraid Users

1. Install the plugin called `UserScripts`
2. Copy and paste the following script file as a new script - [lidarr-hunter.sh](lidarr-hunter.sh) 
3. Ensure to set it to `Run in the background` if your array is already running and set the schedule to `At Startup Array`

<img width="1337" alt="image" src="https://github.com/user-attachments/assets/dbaf9864-1db9-42a5-bd0b-60b6310f9694" />

### SystemD Service

For a more permanent installation on Linux systems using SystemD:

1. Save the script to `/usr/local/bin/lidarr-hunter.sh`
2. Make it executable: `chmod +x /usr/local/bin/lidarr-hunter.sh`
3. Create a systemd service file at `/etc/systemd/system/lidarr-hunter.service`:

```ini
[Unit]
Description=Lidarr Hunter Service
After=network.target lidarr.service

[Service]
Type=simple
User=your-username
Environment="API_KEY=your-api-key"
Environment="API_URL=http://localhost:8686"
Environment="MAX_ITEMS=1"
Environment="SLEEP_DURATION=900"
Environment="RANDOM_SELECTION=true"
Environment="MONITORED_ONLY=false"
Environment="SEARCH_MODE=artist"
ExecStart=/usr/local/bin/lidarr-hunter.sh
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

4. Enable and start the service:

```bash
sudo systemctl enable lidarr-hunter
sudo systemctl start lidarr-hunter
```

## Use Cases

- **Library Completion**: Gradually fill in missing albums and tracks in your collection
- **New Artist Setup**: Automatically find music for newly added artists
- **Background Service**: Run it in the background to continuously maintain your library

## Tips

- **First-Time Use**: Start with default settings to ensure it works with your setup
- **Adjusting Speed**: Lower the `SLEEP_DURATION` to search more frequently (be careful with indexer limits)
- **Multiple Items**: Increase `MAX_ITEMS` if you want to search for more items per cycle
- **Choose the Right Mode**:
  - Use `artist` mode for broad searches (fastest but less targeted)
  - Use `album` mode for more targeted searches
  - Use `song` mode for the most specific searches (slowest but most precise)
- **System Resources**: The script uses minimal resources and can run continuously on even low-powered systems

## Troubleshooting

- **API Key Issues**: Check that your API key is correct in Lidarr settings
- **Connection Problems**: Ensure the Lidarr URL is accessible from where you're running the script
- **Command Failures**: If search commands fail, try using the Lidarr UI to verify what commands are available in your version
- **Logs**: Check the container logs with `docker logs lidarr-hunter` if running in Docker

## Related Projects

* [Sonarr Hunter](https://github.com/plexguide/Sonarr-Hunter) - Sister version for TV shows
* [Radarr Hunter](https://github.com/plexguide/Radarr-Hunter) - Sister version for movies
* [Unraid Intel ARC Deployment](https://github.com/plexguide/Unraid_Intel-ARC_Deployment) - Convert videos to AV1 Format (I've saved 325TB encoding to AV1)
* Visit [PlexGuide](https://plexguide.com) for more great scripts

---

**Change Log:**
- **v1**: Original code written

---

This script helps automate the tedious process of finding and downloading missing music in your collection, running quietly in the background while respecting your indexers' rate limits.
