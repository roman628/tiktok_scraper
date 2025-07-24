#!/bin/bash

echo "Starting TikTok URL Collector Server..."
echo "This server must be running for the Firefox extension to work."
echo "Press Ctrl+C to stop the server."
echo ""

cd "$(dirname "$0")"
python3 url_server.py