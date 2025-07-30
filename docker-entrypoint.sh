#!/bin/bash
set -e

echo "🐳 TikTok Scraper Docker Container Starting..."

# Function to check if a service is running
wait_for_service() {
    local host=$1
    local port=$2
    local service_name=$3
    
    echo "⏳ Waiting for $service_name to be ready..."
    while ! nc -z $host $port; do
        sleep 1
    done
    echo "✅ $service_name is ready!"
}

# Create necessary directories if they don't exist
mkdir -p /app/data /app/downloads /app/models /app/outputs /app/backups /app/logs

# Set permissions
chmod -R 755 /app/data /app/downloads /app/models /app/outputs /app/backups /app/logs

# If selenium-hub is expected, wait for it
if [ "$WAIT_FOR_SELENIUM" = "true" ]; then
    wait_for_service selenium-hub 4444 "Selenium Hub"
fi

# Download ML models if they don't exist
if [ ! -d "/app/models" ] || [ -z "$(ls -A /app/models)" ]; then
    echo "🤖 Downloading ML models..."
    python -c "
import faster_whisper
import os
# Download Whisper model
model = faster_whisper.WhisperModel('base', device='cpu', compute_type='int8')
print('✅ Whisper model downloaded')
"
fi

# Initialize NLTK data if needed
echo "📚 Ensuring NLTK data is current..."
python -c "
import nltk
import ssl
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

nltk.download('punkt', quiet=True)
nltk.download('vader_lexicon', quiet=True)
nltk.download('stopwords', quiet=True)
print('✅ NLTK data ready')
"

# Set Chrome options for headless operation
export CHROME_OPTIONS="--headless --no-sandbox --disable-dev-shm-usage --disable-gpu --window-size=1920,1080"

echo "🚀 Starting application: $@"

# Execute the main command
exec "$@"