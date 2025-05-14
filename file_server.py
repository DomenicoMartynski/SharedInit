from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import logging
from datetime import datetime
import json
import requests

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
STREAMLIT_PORT = 8501  # Port for Streamlit app

# Create Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def ensure_upload_folder():
    """Ensure the upload folder exists."""
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
        logger.info(f"Created directory: {os.path.abspath(UPLOAD_FOLDER)}")

def write_event(event):
    """Write an event to the event file."""
    try:
        # Read existing events
        events = []
        if os.path.exists(EVENT_FILE):
            with open(EVENT_FILE, 'r') as f:
                try:
                    events = json.load(f)
                except json.JSONDecodeError:
                    events = []
        
        # Add new event
        events.append(event)
        
        # Write back to file
        with open(EVENT_FILE, 'w') as f:
            json.dump(events, f)
            
        logger.info(f"Saved file event: {event}")
        print(f"Saved file event: {event}")
            
    except Exception as e:
        logger.error(f"Error saving file event: {str(e)}")
        print(f"Error saving file event: {str(e)}")

@app.route('/downloads_enabled', methods=['POST'])
def check_downloads_enabled():
    """Check if downloads are enabled in the Streamlit app."""
    try:
        logger.info(f"Received request headers: {dict(request.headers)}")
        logger.info(f"Received request data: {request.get_data()}")
        
        # Check content type
        if not request.headers.get('Content-Type', '').startswith('application/json'):
            logger.error(f"Invalid Content-Type: {request.headers.get('Content-Type')}")
            return jsonify({'error': 'Content-Type must be application/json', 'downloads_enabled': False}), 400
            
        # Try to get JSON data
        try:
            data = request.get_json(force=True)  # force=True to try parsing even if content-type is wrong
            logger.info(f"Parsed JSON data: {data}")
        except Exception as e:
            logger.error(f"Failed to parse JSON: {str(e)}")
            return jsonify({'error': 'Invalid JSON data', 'downloads_enabled': False}), 400
        
        downloads_enabled = data.get('downloads_enabled', False)
        logger.info(f"Downloads enabled state: {downloads_enabled}")
        
        return jsonify({'downloads_enabled': downloads_enabled}), 200
    except Exception as e:
        logger.error(f"Error checking downloads status: {str(e)}")
        return jsonify({'error': str(e), 'downloads_enabled': False}), 500

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file uploads."""
    if 'file' not in request.files:
        logger.warning("No file part in request")
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        logger.warning("No selected file")
        return jsonify({'error': 'No selected file'}), 400
    
    try:
        # Check if downloads are enabled by checking the local state
        try:
            # Read the current state from the request headers
            downloads_enabled = request.headers.get('X-Downloads-Enabled', 'true').lower() == 'true'
            logger.info(f"Local downloads_enabled state: {downloads_enabled}")
            
            if not downloads_enabled:
                logger.info("Downloads are disabled, rejecting file upload")
                return jsonify({'message': 'Downloads are currently disabled'}), 403
        except Exception as e:
            logger.error(f"Error checking downloads status: {str(e)}")
            return jsonify({'error': 'Failed to check downloads status'}), 500
        
        ensure_upload_folder()
        
        # Save the file
        file_path = os.path.join(UPLOAD_FOLDER, file.filename)
        logger.info(f"Attempting to save file to: {os.path.abspath(file_path)}")
        file.save(file_path)
        logger.info(f"Successfully saved file to: {os.path.abspath(file_path)}")
        
        # Write file received event
        write_event({
            'type': 'file_received',
            'filename': file.filename,
            'timestamp': datetime.now().isoformat()
        })
        
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
            logger.info("No event file found")
            return jsonify({'events': []}), 200
            
        with open(EVENT_FILE, 'r') as f:
            events = json.load(f)
            logger.info(f"Returning events: {events}")
            print(f"Returning events: {events}")
            
        # Clear the event file after reading
        with open(EVENT_FILE, 'w') as f:
            json.dump([], f)
            
        return jsonify({'events': events}), 200
    except Exception as e:
        logger.error(f"Error checking events: {str(e)}")
        print(f"Error checking events: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({'status': 'healthy'}), 200

if __name__ == '__main__':
    ensure_upload_folder()
    logger.info(f"Starting Flask server on port {PORT}")
    app.run(host='0.0.0.0', port=PORT) 