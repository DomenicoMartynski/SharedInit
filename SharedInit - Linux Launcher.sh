#!/bin/bash

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check if the app is already running
if [ -f ".app_running" ]; then
    # Read PIDs from the file
    while IFS= read -r pid; do
        kill $pid 2>/dev/null
    done < .app_running
    rm .app_running
    exit 0
fi

# Create a virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt > /dev/null 2>&1
else
    source .venv/bin/activate
fi

# Start the Flask server
nohup python file_server.py > /dev/null 2>&1 &
FLASK_PID=$!

# Start the Streamlit app
nohup streamlit run app.py > /dev/null 2>&1 &
STREAMLIT_PID=$!

# Save PIDs to a file
echo $FLASK_PID > .app_running
echo $STREAMLIT_PID >> .app_running 