#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting TikTok URL Collector Server...${NC}"
echo "This server must be running for the Firefox extension to work."
echo -e "${YELLOW}Press Ctrl+C to stop the server.${NC}"
echo ""

# Change to script directory
cd "$(dirname "$0")"

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is not installed${NC}"
    echo "Please install Python 3 to run this server"
    exit 1
fi

# Get Python version
PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo -e "Using Python $PYTHON_VERSION"

# Create data directory if it doesn't exist
if [ ! -d "../data" ]; then
    echo "Creating data directory..."
    mkdir -p ../data
fi

# Check if data directory is writable
if [ ! -w "../data" ]; then
    echo -e "${RED}Error: data directory is not writable${NC}"
    exit 1
fi

echo -e "You can override the default host and port with flags:"
echo -e "  ${YELLOW}./start_server.sh --host YOUR_IP --port YOUR_PORT${NC}"
echo ""

# Run the server, passing all script arguments to the python script
python3 url_server.py "$@"