# Lidarr Hunter - Force Lidarr to Hunt Missing Songs

<h2 align="center">Want to Help? Click the Star in the Upper-Right Corner! ⭐</h2>

**NOTE**  
This utilizes Lidarr API Version - `1`. The Script: [lidarr-hunter.sh](lidarr-hunter.sh)

To run via Docker

```bash
docker run -d --name lidarr-hunter \
  -e API_KEY="your-api-key" \
  -e API_URL="http://your-lidarr-address:8686" \
  -e MAX_ARTISTS="1" \
  -e SLEEP_DURATION="600" \
  -e REFRESH_DURATION="30" \
  -e RANDOM_SELECTION="true" \
  admin9705/lidarr-hunter
```

**Change Log:**
- **v1**: Original code written

![image](https://github.com/user-attachments/assets/3b606e4b-3b6c-4b31-a06e-fb9993266dd5)

### Other Project Guide (Just FYI)

* Sister Version (Sonarr): https://github.com/plexguide/Sonarr-Hunter<br>
* Sister Version (Radarr): https://github.com/plexguide/Radarr-Hunter<br>
* Visit: https://github.com/plexguide/Unraid_Intel-ARC_Deployment - Converts videos to AV1 Format (I've saved 325TB encoding to AV1)
* For other great scripts, visit https://plexguide.com

# Lidarr Missing Music Search Tool

## Overview

This script continually searches your Lidarr library specifically for artists and albums that are missing (monitored but not downloaded) and automatically triggers searches for that missing music. It's designed to run continuously while being gentle on your indexers, helping you gradually complete your music collection.

## Features

- 🔄 **Continuous Operation**: Runs indefinitely until manually stopped
- 🎯 **Direct Missing Music Targeting**: Directly identifies and processes only missing albums and tracks
- 🎲 **Random Selection**: By default, selects missing music randomly to distribute searches across your library
- ⏱️ **Throttled Searches**: Includes configurable delays to prevent overloading indexers
- 📊 **Status Reporting**: Provides clear feedback about what it's doing and which music it's searching for
- 🛡️ **Error Handling**: Gracefully handles connection issues and API failures

## How It Works

1. **Initialization**: Connects to your Lidarr instance and retrieves a list of only monitored artists with missing albums
2. **Selection Process**: Randomly selects a missing album from the filtered list
3. **Refresh**: Refreshes the metadata for the selected artist
4. **Search Trigger**: Uses the AlbumSearch or ArtistSearch command to instruct Lidarr to search for the missing music
5. **Rescan**: Rescans the artist folder to detect any new downloads
6. **Throttling**: After processing an artist, it pauses for a configurable amount of time
7. **Cycling**: After processing the configured number of artists, it starts a new cycle, refreshing the missing music data

## Configuration Options

At the top of the script, you'll find these configurable options:

```bash
API_KEY="your_api_key_here"             # Your Lidarr API key
LIDARR_URL="http://your.lidarr.ip:port" # URL to your Lidarr instance
MAX_ARTISTS=1                           # Artists to process before restarting cycle
SLEEP_DURATION=600                      # Seconds to wait after processing an artist (600=10min)
REFRESH_DURATION="30"                   # This is a pause between multiple artists if MAX_ARTISTS > 1 (a mini sleep)
RANDOM_SELECTION=true                   # true for random selection, false for sequential
```



## Use Cases

- **Library Completion**: Gradually fill in missing albums and tracks in your collection
- **New Artist Setup**: Automatically find music for newly added artists
- **Background Service**: Run it in the background to continuously maintain your library

## How to Run (Unraid Users)

1. Install the plugin called `UserScripts`
2. Copy and paste the following script file as new script - [lidarr-hunter.sh](lidarr-hunter.sh) 
3. Ensure to set it to `Run in the background` if your array is already running and set the schedule to `At Startup Array`

<img width="1337" alt="image" src="https://github.com/user-attachments/assets/dbaf9864-1db9-42a5-bd0b-60b6310f9694" />

## How to Run (Non-Unraid Users)

1. Save the script to a file (e.g., `lidarr-hunter.sh`)
2. Make it executable: `chmod +x lidarr-hunter.sh`
3. Run it: `./lidarr-hunter.sh`

For continuous background operation:
- Use `screen` or `tmux`: `screen -S lidarr-hunter ./lidarr-hunter.sh`
- Or create a systemd service to run it automatically on startup

## Tips

- **First-Time Use**: Start with default settings to ensure it works with your setup
- **Adjusting Speed**: Lower the `SLEEP_DURATION` to search more frequently (be careful with indexer limits)
- **Multiple Artists**: Increase `MAX_ARTISTS` if you want to search for more artists per cycle
- **System Resources**: The script uses minimal resources and can run continuously on even low-powered systems

## Troubleshooting

- **API Key Issues**: Check that your API key is correct in Lidarr settings
- **Connection Problems**: Ensure the Lidarr URL is accessible from where you're running the script
- **Command Failures**: If search commands fail, try using the Lidarr UI to verify what commands are available in your version

---

This script helps automate the tedious process of finding and downloading missing music in your collection, running quietly in the background while respecting your indexers' rate limits.
