import streamlit as st
import socket
import os
import subprocess
import platform
from pathlib import Path
import threading
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import mimetypes
import shutil
import requests
import json
from datetime import datetime
import queue
import ipaddress
import concurrent.futures
from flask import Flask, request, jsonify

# Constants
UPLOAD_FOLDER = "shared_files"
MAX_FILE_SIZE = 200 * 1024 * 1024  # 200MB max file size
PORT = 8501
DOWNLOAD_DIR = "downloads"
BROADCAST_INTERVAL = 10

# Create Flask app for handling file uploads
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    try:
        # Save the file to the downloads directory
        file_path = os.path.join(DOWNLOAD_DIR, file.filename)
        file.save(file_path)
        return jsonify({'message': 'File uploaded successfully'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def start_flask_server():
    """Start the Flask server in a separate thread."""
    app.run(host='0.0.0.0', port=PORT + 1, threaded=True)

# Start Flask server in a separate thread
flask_thread = threading.Thread(target=start_flask_server, daemon=True)
flask_thread.start()

# Configure Streamlit page
st.set_page_config(
    page_title="LAN File Sharing App",
    page_icon="📁",
    layout="wide"
)

# Add custom headers to Streamlit
st.markdown(
    f"""
    <script>
        // Add platform information to headers
        const xhr = new XMLHttpRequest();
        xhr.open('GET', window.location.href);
        xhr.setRequestHeader('X-Platform', '{platform.system()}');
        xhr.setRequestHeader('X-Hostname', '{socket.gethostname()}');
        xhr.setRequestHeader('X-Platform-Version', '{platform.release()}');
        xhr.setRequestHeader('X-Platform-Machine', '{platform.machine()}');
        xhr.send();
    </script>
    """,
    unsafe_allow_html=True
)

# Add platform info to response headers
def add_platform_headers():
    """Add platform information to response headers."""
    st.markdown(
        f"""
        <script>
            // Add platform information to response headers
            const xhr = new XMLHttpRequest();
            xhr.open('GET', window.location.href);
            xhr.setRequestHeader('X-Platform', '{platform.system()}');
            xhr.setRequestHeader('X-Hostname', '{socket.gethostname()}');
            xhr.setRequestHeader('X-Platform-Version', '{platform.release()}');
            xhr.setRequestHeader('X-Platform-Machine', '{platform.machine()}');
            xhr.send();
        </script>
        """,
        unsafe_allow_html=True
    )

# Create necessary directories with proper permissions
def create_directories():
    """Create directories with proper permissions for each platform."""
    try:
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        # Set proper permissions based on platform
        if platform.system() != 'Windows':
            os.chmod(DOWNLOAD_DIR, 0o755)  # rwxr-xr-x
    except Exception as e:
        st.error(f"Error creating directory {DOWNLOAD_DIR}: {str(e)}")

create_directories()

# Initialize session state for active connections if not exists
if 'active_connections' not in st.session_state:
    st.session_state.active_connections = {}

def get_local_ip():
    """Get the local IP address of the machine."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception as e:
        st.warning(f"Could not determine local IP: {str(e)}")
        return "127.0.0.1"

def get_network_range():
    """Get the network range based on local IP."""
    local_ip = get_local_ip()
    ip_parts = local_ip.split('.')
    return f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.0/24"

def check_app_instance(ip):
    """Check if a host is running our Streamlit app."""
    try:
        # Try to connect to the Streamlit port
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.5)  # 500ms timeout for each connection attempt
        result = sock.connect_ex((ip, PORT))
        sock.close()
        
        if result == 0:
            # Try multiple methods to get hostname
            hostname = None
            try:
                # Method 1: Try reverse DNS lookup
                hostname = socket.gethostbyaddr(ip)[0]
            except:
                try:
                    # Method 2: Try to get hostname from the device
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(0.5)
                    sock.connect((ip, PORT))
                    sock.send(b"GET /_stcore/stream HTTP/1.1\r\nHost: " + ip.encode() + b"\r\n\r\n")
                    response = sock.recv(1024).decode()
                    sock.close()
                    
                    # Look for hostname in response headers
                    for line in response.split('\n'):
                        if 'X-Hostname:' in line:
                            hostname = line.split('X-Hostname:')[1].strip()
                            break
                except:
                    pass
            
            # If hostname is still None, use IP as hostname
            if not hostname:
                hostname = ip
            
            # Try to detect platform
            platform_type = "Unknown"
            try:
                # Try multiple endpoints to get platform info
                endpoints = [
                    f"http://{ip}:{PORT}/_stcore/health",
                    f"http://{ip}:{PORT}/_stcore/stream",
                    f"http://{ip}:{PORT}"
                ]
                
                for endpoint in endpoints:
                    try:
                        response = requests.get(endpoint, timeout=0.5)
                        if response.status_code == 200:
                            # Check all possible platform headers
                            platform_type = (
                                response.headers.get('X-Platform') or
                                response.headers.get('X-Platform-Version') or
                                response.headers.get('X-Platform-Machine') or
                                'Unknown'
                            )
                            if platform_type != 'Unknown':
                                break
                    except:
                        continue
                
                # If still unknown, try to detect from hostname and other methods
                if platform_type == "Unknown":
                    try:
                        # Try to detect platform from hostname patterns
                        hostname_lower = hostname.lower()
                        if 'mac' in hostname_lower or 'darwin' in hostname_lower:
                            platform_type = "Darwin"
                        elif 'win' in hostname_lower or 'windows' in hostname_lower or 'pc' in hostname_lower:
                            platform_type = "Windows"
                        elif 'linux' in hostname_lower:
                            platform_type = "Linux"
                        
                        # Additional Windows detection
                        if platform_type == "Unknown":
                            try:
                                # Try to get Windows-specific information
                                response = requests.get(f"http://{ip}:{PORT}/_stcore/stream", timeout=0.5)
                                if response.status_code == 200:
                                    # Check for Windows-specific headers or patterns
                                    if any(win_header in response.headers for win_header in ['X-Windows', 'X-Win32', 'X-Windows-NT']):
                                        platform_type = "Windows"
                                    # Check user agent for Windows
                                    user_agent = response.headers.get('User-Agent', '').lower()
                                    if 'windows' in user_agent or 'win32' in user_agent or 'win64' in user_agent:
                                        platform_type = "Windows"
                            except:
                                pass
                    except:
                        pass
            except:
                pass
            
            return {
                "ip": ip,
                "hostname": hostname,
                "status": "Online",
                "last_seen": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "platform": platform_type
            }
    except:
        pass
    return None

def scan_network():
    """Scan the network for other instances of our app."""
    network = ipaddress.ip_network(get_network_range())
    active_hosts = []
    
    # Get local IP to exclude it from scanning
    local_ip = get_local_ip()
    
    # Get list of IPs to scan (excluding local IP)
    ips_to_scan = [str(ip) for ip in network.hosts() if str(ip) != local_ip]
    total_ips = len(ips_to_scan)
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        future_to_ip = {
            executor.submit(check_app_instance, ip): ip 
            for ip in ips_to_scan
        }
        
        for future in concurrent.futures.as_completed(future_to_ip):
            result = future.result()
            if result:
                active_hosts.append(result)
    
    return active_hosts

def open_file_with_default_app(file_path):
    """Open a file with the default application based on the operating system."""
    try:
        if platform.system() == 'Windows':
            os.startfile(file_path)
        elif platform.system() == 'Darwin':  # macOS
            subprocess.run(['open', file_path])
        else:  # Linux
            subprocess.run(['xdg-open', file_path])
    except Exception as e:
        st.error(f"Error opening file: {str(e)}")

def get_file_mime_type(file_path):
    """Get the MIME type of a file, with platform-specific handling."""
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type is None:
        # Platform-specific MIME type detection
        if platform.system() == 'Darwin':  # macOS
            try:
                output = subprocess.check_output(['file', '--mime-type', file_path]).decode()
                mime_type = output.split(':')[-1].strip()
            except:
                pass
        elif platform.system() == 'Linux':
            try:
                output = subprocess.check_output(['file', '--mime-type', file_path]).decode()
                mime_type = output.split(':')[-1].strip()
            except:
                pass
    return mime_type or 'application/octet-stream'

def broadcast_presence():
    """Broadcast this app's presence to the network."""
    while True:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            
            message = {
                'type': 'presence',
                'ip': get_local_ip(),
                'hostname': socket.gethostname(),
                'platform': platform.system(),
                'timestamp': datetime.now().isoformat()
            }
            
            sock.sendto(json.dumps(message).encode(), ('<broadcast>', PORT))
            sock.close()
            
            time.sleep(BROADCAST_INTERVAL)
        except Exception as e:
            print(f"Broadcast error: {e}")
            time.sleep(BROADCAST_INTERVAL)

def listen_for_broadcasts():
    """Listen for presence broadcasts from other instances."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('', PORT))
    
    while True:
        try:
            data, addr = sock.recvfrom(1024)
            message = json.loads(data.decode())
            
            if message['type'] == 'presence' and message['ip'] != get_local_ip():
                st.session_state.active_connections[message['ip']] = {
                    'ip': message['ip'],
                    'hostname': message['hostname'],
                    'platform': message['platform'],
                    'last_seen': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'status': 'Online'
                }
        except Exception as e:
            print(f"Listen error: {e}")

def start_background_tasks():
    """Start background tasks for broadcasting and listening."""
    if 'broadcast_thread' not in st.session_state:
        st.session_state.broadcast_thread = threading.Thread(target=broadcast_presence, daemon=True)
        st.session_state.broadcast_thread.start()
    
    if 'listen_thread' not in st.session_state:
        st.session_state.listen_thread = threading.Thread(target=listen_for_broadcasts, daemon=True)
        st.session_state.listen_thread.start()

class FileHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory:
            file_path = event.src_path
            if file_path.startswith(os.path.abspath(DOWNLOAD_DIR)):
                st.toast(f"New file received: {os.path.basename(file_path)}")
                open_file_with_default_app(file_path)

def start_file_watcher():
    """Start watching the downloads directory for new files."""
    event_handler = FileHandler()
    observer = Observer()
    observer.schedule(event_handler, DOWNLOAD_DIR, recursive=False)
    observer.start()
    return observer

def is_file_size_allowed(file_size):
    """Check if the file size is within allowed limits."""
    return file_size <= MAX_FILE_SIZE

def get_file_extension(filename):
    """Get the file extension from filename."""
    return os.path.splitext(filename)[1].lower()

def send_file_to_device(file_path, device_ip):
    """Send a file to a specific device."""
    try:
        url = f"http://{device_ip}:{PORT + 1}/upload"  # Use Flask server port
        with open(file_path, 'rb') as f:
            files = {'file': f}
            response = requests.post(url, files=files)
            if response.status_code == 200:
                return True
            else:
                st.error(f"Failed to send file to {device_ip}: {response.text}")
                return False
    except Exception as e:
        st.error(f"Error sending file to {device_ip}: {str(e)}")
        return False

def broadcast_file(file_path):
    """Send a file to all connected devices."""
    success_count = 0
    total_devices = len(st.session_state.active_connections)
    
    if total_devices == 0:
        st.warning("No devices connected to broadcast to.")
        return
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, (ip, device) in enumerate(st.session_state.active_connections.items()):
        status_text.text(f"Sending to {device['hostname']} ({ip})...")
        if send_file_to_device(file_path, ip):
            success_count += 1
        progress_bar.progress((i + 1) / total_devices)
    
    progress_bar.empty()
    status_text.empty()
    
    if success_count == total_devices:
        st.success(f"Successfully sent file to all {total_devices} devices!")
    else:
        st.warning(f"Sent file to {success_count} out of {total_devices} devices.")

def main():
    st.title("LAN File Sharing App")
    
    # Display local IP address and platform
    local_ip = get_local_ip()
    st.info(f"Your local IP address: {local_ip}")
    st.info(f"Platform: {platform.system()} {platform.release()}")
    
    # Perform initial scan if not done yet
    if 'initial_scan_done' not in st.session_state:
        with st.spinner("Performing initial network scan..."):
            active_hosts = scan_network()
            st.session_state.active_connections = {
                host['ip']: host for host in active_hosts
            }
            st.session_state.initial_scan_done = True
    
    # Start background tasks
    start_background_tasks()
    
    # Create downloads directory if it doesn't exist
    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR)
    
    # File upload section
    st.header("Send Files")
    
    # Define allowed file types in a more user-friendly way
    allowed_types = {
        "Adobe Files": ["psd", "ai", "indd", "pdf", "prproj", "aep", "lrcat", "sesx"],
        "Microsoft Office": ["doc", "docx", "xls", "xlsx", "ppt", "pptx", "pub", "vsd", "mdb", "accdb", "one"],
        "Autodesk": ["dwg", "dxf", "rvt", "rfa", "max", "ma", "mb", "ipt", "iam", "f3d", "nwd"],
        "Images": ["jpg", "jpeg", "png", "gif", "bmp", "tiff", "tif", "svg", "webp", "ico", "raw", "cr2", "nef", "arw", "dng"],
        "Media": ["mp4", "avi", "mov", "wmv", "flv", "mkv", "mp3", "wav", "ogg", "flac", "m4a", "aac", "wma"],
        "Archives": ["zip", "rar", "7z", "tar", "gz", "bz2"],
        "Documents": ["txt", "rtf", "csv", "json", "xml", "html", "htm", "css", "js", "py", "java", "cpp", "c", "h", "sql"]
    }
    
    # Flatten the allowed types for the actual file uploader
    all_extensions = [ext for extensions in allowed_types.values() for ext in extensions]
    
    uploaded_file = st.file_uploader(
        "Choose a file to send",
        type=all_extensions,
        accept_multiple_files=False,
        key="file_uploader"
    )
    
    if uploaded_file is not None:
        try:
            # Check file size
            file_size = uploaded_file.size
            if not is_file_size_allowed(file_size):
                st.error(f"File size exceeds the maximum limit of {MAX_FILE_SIZE / (1024*1024)}MB")
                return

            # Get file extension
            file_extension = get_file_extension(uploaded_file.name)
            if file_extension[1:] not in all_extensions:
                st.error(f"File type {file_extension} is not allowed")
                return

            # Save the uploaded file
            file_path = os.path.join(DOWNLOAD_DIR, uploaded_file.name)
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            # Broadcast the file to all connected devices
            broadcast_file(file_path)
            
        except Exception as e:
            st.error(f"Error uploading file: {str(e)}")
            st.error("Please try again with a different file or check file permissions.")
    
    # Display connected devices
    st.header("Connected Devices")
    if st.session_state.active_connections:
        for ip, device in st.session_state.active_connections.items():
            st.write(f"📱 {device['hostname']} ({ip}) - {device['status']}")
    else:
        st.info("No other devices connected. Start the app on other devices to enable file sharing.")
    
    # Display received files
    st.header("Received Files")
    files = os.listdir(DOWNLOAD_DIR)
    if files:
        for file in files:
            file_path = os.path.join(DOWNLOAD_DIR, file)
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(file)
            with col2:
                if st.button("Open", key=file):
                    open_file_with_default_app(file_path)
    else:
        st.info("No files received yet.")
    
    # Supported Applications Section - Concise Version (moved to end)
    st.markdown("---")
    st.header("📚 Supported Applications")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        ### Main Applications
        - 🎨 **Adobe Creative Suite** (Photoshop, Illustrator, InDesign, etc.)
        - 💼 **Microsoft Office** (Word, Excel, PowerPoint, etc.)
        - 🏗️ **Autodesk** (AutoCAD, Revit, 3ds Max, etc.)
        """)
    
    with col2:
        st.markdown("""
        ### Other Formats
        - 🖼️ **Images** (JPG, PNG, RAW, etc.)
        - 🎥 **Media** (MP4, MP3, etc.)
        - 📦 **Archives** (ZIP, RAR, etc.)
        """)
    
    st.markdown("""
    > 💡 For a complete list of supported formats and detailed documentation, 
    > visit the [documentation](documentation) page.
    """)

if __name__ == "__main__":
    # Start file watcher in a separate thread
    observer = start_file_watcher()
    try:
        main()
    finally:
        observer.stop()
        observer.join() 