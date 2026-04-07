#!/bin/bash
# scripts/browser_launcher.sh
# Launcher for browsers with remote debugging enabled.

# Usage: ./browser_launcher.sh [brave|chrome|firefox] [url]

BROWSER=$1
URL=$2
DEBUG_PORT=9222

if [ -z "$BROWSER" ]; then
    echo "Usage: ./browser_launcher.sh [brave|chrome|firefox] [url]"
    exit 1
fi

case $BROWSER in
    brave)
        /snap/bin/brave --remote-debugging-port=$DEBUG_PORT $URL &
        ;;
    chrome)
        /usr/bin/google-chrome --remote-debugging-port=$DEBUG_PORT $URL &
        ;;
    firefox)
        /usr/bin/firefox --remote-debugger $URL &
        ;;
    *)
        echo "Unknown browser: $BROWSER"
        exit 1
        ;;
esac
