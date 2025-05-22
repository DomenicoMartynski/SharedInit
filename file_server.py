from flask import Flask, request, jsonify, send_from_directory
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
CONFIG_FILE = "app_config.json"
MAX_FILE_SIZE = 200 * 1024 * 1024  # 200MB max file size
PORT = 8502  # Different port from Streamlit
EVENT_FILE = "file_events.json"  # File to store events for Streamlit to read
STREAMLIT_PORT = 8501  # Port for Streamlit app

# Get the project root directory
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DEFAULT_UPLOAD_FOLDER = os.path.join(PROJECT_ROOT, "downloads")

def load_config():
    """Load configuration from file."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                # If a custom folder is configured, use it
                if "download_folder" in config:
                    return config
        except:
            pass
    # Return default configuration
    return {"download_folder": DEFAULT_UPLOAD_FOLDER}

# Load the configured upload folder
config = load_config()
UPLOAD_FOLDER = config.get("download_folder", DEFAULT_UPLOAD_FOLDER)

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
        events = []
        if os.path.exists(EVENT_FILE):
            with open(EVENT_FILE, 'r') as f:
                try:
                    events = json.load(f)
                except json.JSONDecodeError:
                    events = []
        
        events.append(event)
        
        with open(EVENT_FILE, 'w') as f:
            json.dump(events, f)
            f.flush()
    except Exception as e:
        logger.error(f"Error writing event: {str(e)}")

@app.route('/downloads_enabled', methods=['POST'])
def check_downloads_enabled():
    """Check if downloads are enabled."""
    try:
        if os.path.exists("downloads_state.json"):
            with open("downloads_state.json", "r") as f:
                state = json.load(f)
                return jsonify({"downloads_enabled": state.get("downloads_enabled", True)})
        return jsonify({"downloads_enabled": True})
    except Exception as e:
        logger.error(f"Error checking downloads state: {str(e)}")
        return jsonify({"downloads_enabled": True})

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
            if os.path.exists("downloads_state.json"):
                with open("downloads_state.json", "r") as f:
                    state = json.load(f)
                    downloads_enabled = state.get("downloads_enabled", True)
            else:
                downloads_enabled = True
                
            if not downloads_enabled:
                logger.info("Downloads are disabled, rejecting file upload")
                return jsonify({'message': 'Downloads are currently disabled'}), 403
        except Exception as e:
            logger.error(f"Error checking downloads status: {str(e)}")
            return jsonify({'error': 'Failed to check downloads status'}), 500
        
        ensure_upload_folder()
        
        # Create the full path including any subdirectories
        file_path = os.path.join(UPLOAD_FOLDER, file.filename)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # Save the file
        logger.info(f"Attempting to save file to: {os.path.abspath(file_path)}")
        file.save(file_path)
        logger.info(f"Successfully saved file to: {os.path.abspath(file_path)}")
        
        # Check if it's a zip file and extract it
        if file.filename.lower().endswith('.zip'):
            try:
                import zipfile
                import shutil
                
                # Create a temporary directory for extraction
                temp_dir = os.path.join(UPLOAD_FOLDER, f"temp_extract_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
                os.makedirs(temp_dir, exist_ok=True)
                
                # Extract the zip file
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)
                
                # Track newly extracted files
                extracted_files = []
                
                # Move extracted files to their final location
                for root, dirs, files in os.walk(temp_dir):
                    for dir_name in dirs:
                        src_dir = os.path.join(root, dir_name)
                        dst_dir = os.path.join(UPLOAD_FOLDER, os.path.relpath(src_dir, temp_dir))
                        os.makedirs(dst_dir, exist_ok=True)
                    
                    for file_name in files:
                        src_file = os.path.join(root, file_name)
                        dst_file = os.path.join(UPLOAD_FOLDER, os.path.relpath(src_file, temp_dir))
                        os.makedirs(os.path.dirname(dst_file), exist_ok=True)
                        shutil.move(src_file, dst_file)
                        extracted_files.append(os.path.relpath(dst_file, UPLOAD_FOLDER))
                
                # Clean up
                shutil.rmtree(temp_dir)
                os.remove(file_path)  # Remove the original zip file
                
                # Write file received event only for newly extracted files
                for extracted_file in extracted_files:
                    write_event({
                        'type': 'file_received',
                        'filename': extracted_file,
                        'timestamp': datetime.now().isoformat(),
                        'is_extracted': True  # Add flag to indicate this is from extraction
                    })
                
                return jsonify({'message': 'Zip file extracted successfully'}), 200
                
            except Exception as e:
                logger.error(f"Error extracting zip file: {str(e)}")
                # If extraction fails, keep the zip file
                write_event({
                    'type': 'file_received',
                    'filename': file.filename,
                    'timestamp': datetime.now().isoformat()
                })
                return jsonify({'message': 'File uploaded successfully (extraction failed)'}), 200
        
        # Write file received event for non-zip files
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

@app.route('/update_config', methods=['POST'])
def update_config():
    """Update server configuration."""
    try:
        data = request.get_json()
        if 'download_folder' in data:
            new_folder = data['download_folder']
            # Update the global UPLOAD_FOLDER
            global UPLOAD_FOLDER
            UPLOAD_FOLDER = new_folder
            app.config['UPLOAD_FOLDER'] = new_folder
            
            # Ensure the folder exists
            ensure_upload_folder()
            
            # Save the new configuration
            config = load_config()
            config['download_folder'] = new_folder
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f)
                
            return jsonify({'message': 'Configuration updated successfully'}), 200
        return jsonify({'error': 'Invalid configuration data'}), 400
    except Exception as e:
        logger.error(f"Error updating configuration: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/download/<path:filename>', methods=['GET'])
def download_file(filename):
    """Download a file or folder."""
    try:
        # Convert URL-encoded backslashes to forward slashes
        filename = filename.replace('\\', '/')
        
        # Normalize the path to prevent directory traversal
        file_path = os.path.normpath(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
        # Ensure the path is within the upload folder
        if not os.path.abspath(file_path).startswith(os.path.abspath(app.config['UPLOAD_FOLDER'])):
            return jsonify({'error': 'Access denied'}), 403
        
        # Check if path exists
        if not os.path.exists(file_path):
            logger.error(f"File/folder not found: {file_path}")
            return jsonify({'error': 'File or folder not found'}), 404
            
        # If it's a directory, create a zip file
        if os.path.isdir(file_path):
            import tempfile
            import zipfile
            
            # Create a temporary zip file
            temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
            with zipfile.ZipFile(temp_zip.name, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Walk through the directory
                for root, dirs, files in os.walk(file_path):
                    for file in files:
                        file_full_path = os.path.join(root, file)
                        # Get the relative path for the file in the zip
                        arcname = os.path.relpath(file_full_path, app.config['UPLOAD_FOLDER'])
                        zipf.write(file_full_path, arcname)
            
            # Send the zip file
            response = send_from_directory(
                os.path.dirname(temp_zip.name),
                os.path.basename(temp_zip.name),
                as_attachment=True,
                download_name=f"{os.path.basename(filename)}.zip"
            )
            
            # Clean up the temporary file after sending
            @response.call_on_close
            def cleanup():
                try:
                    os.unlink(temp_zip.name)
                except:
                    pass
                    
            return response
        else:
            # For regular files, send as before
            directory = os.path.dirname(file_path)
            filename = os.path.basename(file_path)
            return send_from_directory(directory, filename, as_attachment=True)
    except Exception as e:
        logger.error(f"Error sending file/folder {filename}: {str(e)}")
        return jsonify({'error': f'Failed to download file/folder: {str(e)}'}), 500

if __name__ == '__main__':
    ensure_upload_folder()
    logger.info(f"Starting Flask server on port {PORT}")
    app.run(host='0.0.0.0', port=PORT) 