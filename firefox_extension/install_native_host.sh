#!/bin/bash

# Firefox native messaging host installation script

NATIVE_HOST_DIR="$HOME/.mozilla/native-messaging-hosts"
MANIFEST_FILE="tiktok_url_collector.json"

mkdir -p "$NATIVE_HOST_DIR"

cp "$MANIFEST_FILE" "$NATIVE_HOST_DIR/"

echo "Native messaging host installed to: $NATIVE_HOST_DIR/$MANIFEST_FILE"
echo ""
echo "To install the Firefox extension:"
echo "1. Open Firefox"
echo "2. Go to about:debugging"
echo "3. Click 'This Firefox'"
echo "4. Click 'Load Temporary Add-on'"
echo "5. Select the manifest.json file in this directory"
echo ""
echo "The extension will automatically capture TikTok video URLs and add them to urls.txt"