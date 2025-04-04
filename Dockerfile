# Start from a lightweight Python image
FROM python:3.10-slim

# Set default environment variables (non-sensitive only!)
# We remove API_KEY to avoid baking secrets into the image
ENV API_URL="http://your-lidarr-address:8686" \
    SEARCH_TYPE="both" \
    SEARCH_MODE="artist" \
    MAX_MISSING="1" \
    MAX_UPGRADES="5" \
    SLEEP_DURATION="900" \
    RANDOM_SELECTION="true" \
    MONITORED_ONLY="true" \
    STATE_RESET_INTERVAL_HOURS="168" \
    DEBUG_MODE="false"

# Create a directory for our script and state files
RUN mkdir -p /app && mkdir -p /tmp/huntarr-lidarr-state

# Switch working directory
WORKDIR /app

# Install Python dependencies (requests is needed by huntarr-lidarr script)
RUN pip install --no-cache-dir requests

# Copy the Python script into the container
# Make sure this matches your actual filename if it's e.g. "huntarr-lidarr.py"
COPY huntarr.py /app/huntarr.py

# Make the script executable (optional but good practice)
RUN chmod +x /app/huntarr.py

# Add a simple HEALTHCHECK (optional)
HEALTHCHECK --interval=5m --timeout=3s \
  CMD pgrep -f huntarr.py || exit 1

# Run your Python script as the container's entrypoint
ENTRYPOINT ["python", "huntarr.py"]
