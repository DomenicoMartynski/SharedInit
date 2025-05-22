#!/bin/bash

echo "=== Test Script Running ==="
echo "Current date and time: $(date)"
echo "Operating System: $(uname -s)"
echo "Hostname: $(hostname)"
echo "Current user: $(whoami)"
echo "Current directory: $(pwd)"
echo "=== Script Completed ==="

# Add a pause so the window doesn't close immediately
read -p "Press Enter to close this window..." 