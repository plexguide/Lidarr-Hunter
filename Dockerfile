FROM python:3.9-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY main.py config.py api.py ./
COPY missing/ ./missing/
COPY upgrade/ ./upgrade/
COPY utils/ ./utils/

# Default environment variables
ENV API_KEY="your-api-key" \
    API_URL="http://your-lidarr-address:8686" \
    MAX_ITEMS=1 \
    SLEEP_DURATION=900 \
    RANDOM_SELECTION="true" \
    MONITORED_ONLY="true" \
    SEARCH_MODE="artist" \
    SEARCH_TYPE="missing" \
    DEBUG_MODE="false"

# Run the application
CMD ["python", "main.py"]