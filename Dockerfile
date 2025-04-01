# Use a lightweight Alpine Linux base image
FROM alpine:latest

# Install bash, curl, and jq (required by the script)
RUN apk add --no-cache bash curl jq

# Set default environment variables for Lidarr Hunter
ENV API_KEY="your-api-key" \
    API_URL="http://your-lidarr-address:8686" \
    SEARCH_MODE="artist" \
    MONITORED_ONLY="false" \
    MAX_ITEMS="1" \
    SLEEP_DURATION="900" \
    RANDOM_SELECTION="true"

# Copy your lidarr-hunter.sh script into the container
COPY lidarr-hunter.sh /usr/local/bin/lidarr-hunter.sh

# Make the script executable
RUN chmod +x /usr/local/bin/lidarr-hunter.sh

# Set the default command to run the script
ENTRYPOINT ["/usr/local/bin/lidarr-hunter.sh"]
