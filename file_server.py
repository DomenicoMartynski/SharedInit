from flask import Flask, request, jsonify
import os
import logging
from datetime import datetime
import json
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
UPLOAD_FOLDER = "downloads"
MAX_FILE_SIZE = 200 * 1024 * 1024  # 200MB max file size
PORT = 8502  # Different port from Streamlit
EVENT_FILE = "file_events.json"  # File to store events for Streamlit to read
RERUN_SIGNAL_FILE = "rerun_signal.txt"  # Signal file to trigger Streamlit rerun

# Create Flask app
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
logger.info(f"Upload folder path: {os.path.abspath(UPLOAD_FOLDER)}")

def trigger_streamlit_rerun():
    """Create a signal file to trigger Streamlit rerun."""
    try:
        # Write current timestamp to signal file
        with open(RERUN_SIGNAL_FILE, 'w') as f:
            f.write(str(time.time()))
        logger.info("Created rerun signal file")
    except Exception as e:
        logger.error(f"Error creating rerun signal: {str(e)}")

def save_file_event(event_type, filename):
    """Save file event to the event file."""
    try:
        # Read existing events
        events = []
        if os.path.exists(EVENT_FILE):
            with open(EVENT_FILE, 'r') as f:
                events = json.load(f)
        
        # Add new event
        events.append({
            'type': event_type,
            'filename': filename,
            'timestamp': datetime.now().isoformat()
        })
        
        # Save updated events
        with open(EVENT_FILE, 'w') as f:
            json.dump(events, f)
            
        logger.info(f"Saved file event: {event_type} for {filename}")
        
        # Trigger Streamlit rerun
        trigger_streamlit_rerun()
            
    except Exception as e:
        logger.error(f"Error saving file event: {str(e)}")

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file uploads."""
    logger.info("Received file upload request")
    
    if 'file' not in request.files:
        logger.warning("No file part in request")
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        logger.warning("No selected file")
        return jsonify({'error': 'No selected file'}), 400
    
    try:
        # Save the file
        file_path = os.path.join(UPLOAD_FOLDER, file.filename)
        logger.info(f"Attempting to save file to: {os.path.abspath(file_path)}")
        logger.info(f"Current working directory: {os.getcwd()}")
        
        # Ensure the upload folder exists
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        
        # Save the file
        file.save(file_path)
        logger.info(f"Successfully saved file to: {os.path.abspath(file_path)}")
        logger.info(f"File size: {os.path.getsize(file_path)} bytes")
        
        # Save file event for Streamlit to pick up
        save_file_event('file_received', file.filename)
        
        return jsonify({'message': 'File uploaded successfully'}), 200
    except Exception as e:
        logger.error(f"Error saving file: {str(e)}")
        logger.error(f"Current working directory: {os.getcwd()}")
        logger.error(f"Attempted to save to: {os.path.abspath(file_path)}")
        return jsonify({'error': f"Failed to upload file: {str(e)}"}), 500

@app.route('/check_events', methods=['GET'])
def check_events():
    """Check for new file events."""
    try:
        if not os.path.exists(EVENT_FILE):
            return jsonify({'events': []}), 200
            
        with open(EVENT_FILE, 'r') as f:
            events = json.load(f)
            
        # Clear the event file after reading
        with open(EVENT_FILE, 'w') as f:
            json.dump([], f)
            
        return jsonify({'events': events}), 200
    except Exception as e:
        logger.error(f"Error checking events: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({'status': 'healthy'}), 200

if __name__ == '__main__':
    logger.info(f"Starting Flask server on port {PORT}")
    logger.info(f"Upload folder: {os.path.abspath(UPLOAD_FOLDER)}")
    app.run(host='0.0.0.0', port=PORT) 