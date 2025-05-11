from flask import Flask, request, jsonify
import os
import logging
from datetime import datetime
import json

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

# Create Flask app
app = Flask(__name__)
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
        new_event = {
            'type': event_type,
            'filename': filename,
            'timestamp': datetime.now().isoformat()
        }
        events.append(new_event)
        
        # Write back to file
        with open(EVENT_FILE, 'w') as f:
            json.dump(events, f)
            
        logger.info(f"Saved file event: {new_event}")
        print(f"Saved file event: {new_event}")
        
        # Trigger Streamlit rerun
        trigger_streamlit_rerun()
            
    except Exception as e:
        logger.error(f"Error saving file event: {str(e)}")
        print(f"Error saving file event: {str(e)}")

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