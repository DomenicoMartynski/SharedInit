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
import logging
import sys
import site

# Version compatibility check
PYTHON_VERSION = sys.version_info
MIN_PYTHON_VERSION = (3, 8)
if PYTHON_VERSION < MIN_PYTHON_VERSION:
    raise RuntimeError(f"Python {MIN_PYTHON_VERSION[0]}.{MIN_PYTHON_VERSION[1]} or higher is required. You are using Python {PYTHON_VERSION[0]}.{PYTHON_VERSION[1]}")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DEFAULT_UPLOAD_FOLDER = os.path.join(PROJECT_ROOT, "downloads")
MAX_FILE_SIZE = 200 * 1024 * 1024  # 200MB max file size
STREAMLIT_PORT = 8501
FLASK_PORT = 8502
BROADCAST_INTERVAL = 10
EVENT_FILE = "file_events.json"
CONFIG_FILE = "app_config.json"

# Create a thread-safe queue for communication
connection_queue = queue.Queue()
file_event_queue = queue.Queue()

# Compatibility layer for different Python versions
def create_thread(target, daemon=True):
    """Create a thread with version-specific handling."""
    try:
        # Python 3.13+ style
        thread = threading.Thread(target=target, daemon=daemon)
    except TypeError:
        # Python 3.8-3.12 style
        thread = threading.Thread(target=target)
        thread.daemon = daemon
    return thread

def join_thread(thread, timeout=None):
    """Join a thread with version-specific handling."""
    try:
        thread.join(timeout=timeout)
    except Exception as e:
        logger.error(f"Error joining thread: {str(e)}")
        # Fallback for older Python versions
        if timeout is not None:
            thread.join()

def install_matlab_engine():
    """Install MATLAB Engine API for Python in the virtual environment."""
    try:
        # Check multiple possible MATLAB installation paths
        possible_paths = []
        
        if platform.system() == 'Windows':
            possible_paths = [
                r"C:\Program Files\MATLAB",
                r"C:\Program Files (x86)\MATLAB",
                os.path.expanduser("~\\AppData\\Local\\Programs\\MATLAB")
            ]
        elif platform.system() == 'Darwin':  # macOS
            possible_paths = [
                "/Applications/MATLAB",
                os.path.expanduser("~/Applications/MATLAB"),
                "/usr/local/MATLAB"
            ]
        else:  # Linux
            possible_paths = [
                "/usr/local/MATLAB",
                "/opt/MATLAB",
                os.path.expanduser("~/MATLAB")
            ]
        
        # Add environment variable path if set
        matlab_env_path = os.environ.get('MATLAB_HOME')
        if matlab_env_path:
            possible_paths.insert(0, matlab_env_path)
        
        matlab_path = None
        for path in possible_paths:
            if os.path.exists(path):
                matlab_path = path
                break
        
        if not matlab_path:
            logger.warning("MATLAB installation not found in any standard location")
            logger.info("Please ensure MATLAB is installed and set the MATLAB_HOME environment variable to your MATLAB installation path")
            return False
        
        # Find the latest MATLAB version
        matlab_versions = []
        for item in os.listdir(matlab_path):
            item_path = os.path.join(matlab_path, item)
            if os.path.isdir(item_path) and (item.startswith('R') or item.startswith('matlab')):
                matlab_versions.append(item)
        
        if not matlab_versions:
            logger.warning(f"No MATLAB versions found in {matlab_path}")
            return False
        
        # Sort versions and get the latest
        latest_version = sorted(matlab_versions)[-1]
        engine_path = os.path.join(matlab_path, latest_version, 'extern', 'engines', 'python')
        
        if not os.path.exists(engine_path):
            logger.warning(f"MATLAB Engine API not found in {engine_path}")
            return False
        
        # Get the Python executable path
        python_exe = sys.executable
        
        # Install MATLAB Engine API
        try:
            logger.info(f"Installing MATLAB Engine API from {engine_path}")
            result = subprocess.run(
                [python_exe, 'setup.py', 'install'],
                cwd=engine_path,
                check=True,
                capture_output=True,
                text=True
            )
            logger.info("Successfully installed MATLAB Engine API")
            logger.debug(f"Installation output: {result.stdout}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Error installing MATLAB Engine API: {e.stderr}")
            logger.error(f"Command output: {e.stdout}")
            return False
            
    except Exception as e:
        logger.error(f"Error during MATLAB Engine API installation: {str(e)}")
        return False

# Initialize MATLAB engine
MATLAB_AVAILABLE = False
matlab_engine = None

try:
    import matlab.engine
    matlab_engine = matlab.engine.start_matlab()
    MATLAB_AVAILABLE = True
    logger.info("Successfully initialized MATLAB engine")
except ImportError:
    logger.info("MATLAB Engine API not found. Attempting to install...")
    if install_matlab_engine():
        try:
            # Reload site packages to ensure the new installation is recognized
            import site
            site.main()
            import matlab.engine
            matlab_engine = matlab.engine.start_matlab()
            MATLAB_AVAILABLE = True
            logger.info("Successfully initialized MATLAB engine after installation")
        except Exception as e:
            logger.error(f"Failed to initialize MATLAB after installation: {str(e)}")
    else:
        logger.warning("Failed to install MATLAB Engine API. MATLAB functionality will be disabled.")
except Exception as e:
    logger.warning(f"MATLAB engine initialization failed: {str(e)}")
    logger.warning("MATLAB functionality will be disabled.")

def execute_matlab_script(script_path):
    """Execute a MATLAB script file."""
    if not MATLAB_AVAILABLE:
        st.error("MATLAB engine is not available. Please ensure MATLAB is installed and properly configured.")
        return False
    
    try:
        # Get the directory of the script
        script_dir = os.path.dirname(script_path)
        # Change MATLAB's current directory to the script's directory
        matlab_engine.cd(script_dir)
        # Execute the script
        matlab_engine.run(script_path)
        return True
    except Exception as e:
        st.error(f"Error executing MATLAB script: {str(e)}")
        return False

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
    return {"download_folder": DEFAULT_UPLOAD_FOLDER, "max_path": ""}

# Initialize session state
if 'active_connections' not in st.session_state:
    st.session_state.active_connections = {}
if 'last_file_count' not in st.session_state:
    st.session_state.last_file_count = 0
if 'last_received_file' not in st.session_state:
    st.session_state.last_received_file = None
if 'current_session_files' not in st.session_state:
    st.session_state.current_session_files = set()
if 'background_threads_started' not in st.session_state:
    st.session_state.background_threads_started = False
if 'last_upload_status' not in st.session_state:
    st.session_state.last_upload_status = None
if 'last_upload_time' not in st.session_state:
    st.session_state.last_upload_time = None
if 'last_deletion_status' not in st.session_state:
    st.session_state.last_deletion_status = None
if 'last_deletion_time' not in st.session_state:
    st.session_state.last_deletion_time = None
if 'last_event_check' not in st.session_state:
    st.session_state.last_event_check = datetime.now()
if 'download_folder' not in st.session_state:
    config = load_config()
    st.session_state.download_folder = config.get("download_folder", DEFAULT_UPLOAD_FOLDER)
if 'max_path' not in st.session_state:
    config = load_config()
    st.session_state.max_path = config.get("max_path", "")

# Update UPLOAD_FOLDER to use the configured folder
UPLOAD_FOLDER = st.session_state.download_folder

def find_3ds_max():
    """Find 3ds Max installation using the configured path."""
    if platform.system() != 'Windows':
        return None
    
    # Use the configured path if available
    if hasattr(st.session_state, 'max_path') and st.session_state.max_path:
        if os.path.exists(st.session_state.max_path):
            logger.info(f"Using configured 3ds Max path: {st.session_state.max_path}")
            return st.session_state.max_path
        else:
            logger.error(f"Configured 3ds Max path does not exist: {st.session_state.max_path}")
    
    logger.error("3ds Max installation not found. Please configure the path in the Connected Devices section.")
    return None

def check_file_events():
    """Check for new file events."""
    try:
        # Get events from Flask server
        response = requests.get(f"http://localhost:{FLASK_PORT}/check_events")
        if response.status_code == 200:
            events = response.json().get('events', [])
            logger.info(f"Received events from Flask: {events}")
            print(f"Received events from Flask: {events}")
            
            # Check if any of the events are from a zip file
            is_zip_event = any(event.get('filename', '').lower().endswith('.zip') for event in events)
            
            # Check if any of the events are script files
            has_script_files = any(
                get_file_extension(event.get('filename', '')).lower() in ['.sh', '.bash', '.zsh', '.ms']
                for event in events
            )
            
            # Process new events
            for event in events:
                if event['type'] == 'file_received':
                    filename = event['filename']
                    file_extension = get_file_extension(filename).lower()
                    is_script = file_extension in ['.sh', '.bash', '.zsh', '.ms']
                    
                    # Update session state
                    st.session_state.last_received_file = filename
                    logger.info(f"Setting last_received_file to: {filename}")
                    print(f"Setting last_received_file to: {filename}")
                    
                    st.session_state.last_upload_status = {
                        'success': f"File {filename} received successfully"
                    }
                    st.session_state.last_upload_time = datetime.now()
                    
                    # Show success message
                    if is_script:
                        st.success(f"📥 New script received and executed: {filename}")
                    else:
                        st.success(f"📥 New file received: {filename}")
                    
                    # Show toast notification
                    if is_script:
                        st.toast(f"📥 New script received and executed: {filename}")
                    else:
                        st.toast(f"📥 New file received: {filename}")
                    
                    # Handle file based on type
                    file_path = os.path.join(UPLOAD_FOLDER, filename)
                    if os.path.exists(file_path):
                        if is_script:
                            logger.info(f"Processing script file: {filename}")
                            # For .ms files, execute directly without opening
                            if file_extension == '.ms':
                                logger.info("Processing .ms file")
                                if platform.system() == 'Windows':
                                    # Find 3ds Max installation
                                    max_exe = find_3ds_max()
                                    
                                    if max_exe:
                                        # Create a batch file to execute the script
                                        batch_file = os.path.join(os.path.dirname(file_path), "run_max_script.bat")
                                        with open(batch_file, 'w') as f:
                                            f.write(f'@echo off\n')
                                            f.write(f'echo Executing 3ds Max script: {os.path.basename(file_path)}\n')
                                            f.write(f'"{max_exe}" -U MAXScript "{file_path}"\n')
                                            f.write(f'echo Script execution completed.\n')
                                            f.write(f'pause\n')
                                        
                                        # Execute the batch file in a new console window
                                        subprocess.Popen(['cmd.exe', '/c', 'start', 'cmd.exe', '/k', batch_file],
                                                      creationflags=subprocess.CREATE_NEW_CONSOLE)
                                        
                                        # Schedule cleanup of the batch file
                                        def cleanup_batch():
                                            try:
                                                # Wait indefinitely for the flag file to appear (indicating render is complete)
                                                wait_interval = 1  # Check every second
                                                
                                                while True:
                                                    if os.path.exists(os.path.join(os.path.dirname(file_path), "render_complete.flag")):
                                                        # Render is complete, clean up both files
                                                        if os.path.exists(batch_file):
                                                            os.remove(batch_file)
                                                        return
                                                    time.sleep(wait_interval)
                                                
                                            except Exception as e:
                                                print(f"Error in cleanup: {e}")
                                                # Try to clean up anyway
                                                try:
                                                    if os.path.exists(batch_file):
                                                        os.remove(batch_file)
                                                except:
                                                    pass
                                        
                                        create_thread(target=cleanup_batch).start()
                                    else:
                                        st.error("3ds Max installation not found. Please ensure 3ds Max is installed.")
                                else:
                                    st.warning("3ds Max scripts can only be executed on Windows.")
                            else:
                                # For other script types, execute them immediately
                                if file_extension in ['.sh', '.bash']:
                                    logger.info(f"Processing .sh/.bash file: {filename}")
                                    if platform.system() == 'Darwin':  # macOS
                                        try:
                                            logger.info("Processing on macOS")
                                            # Get absolute paths
                                            abs_file_path = os.path.abspath(file_path)
                                            abs_script_dir = os.path.dirname(abs_file_path)
                                            script_name = os.path.basename(abs_file_path)
                                            
                                            logger.info(f"Absolute file path: {abs_file_path}")
                                            logger.info(f"Script directory: {abs_script_dir}")
                                            logger.info(f"Script name: {script_name}")
                                            
                                            # Read the script content and fix line endings
                                            with open(abs_file_path, 'rb') as f:
                                                content = f.read()
                                            
                                            # Convert to string and fix line endings
                                            content = content.decode('utf-8', errors='ignore')
                                            content = content.replace('\r\n', '\n').replace('\r', '\n')
                                            
                                            # Ensure proper shebang line and remove any BOM
                                            if content.startswith('\ufeff'):
                                                content = content[1:]
                                            if not content.startswith('#!/bin/bash'):
                                                content = '#!/bin/bash\n' + content
                                            
                                            # Ensure script ends with a newline
                                            if not content.endswith('\n'):
                                                content += '\n'
                                            
                                            # Write back the fixed content with Unix line endings
                                            with open(abs_file_path, 'w', newline='\n') as f:
                                                f.write(content)
                                            
                                            # Make executable
                                            os.chmod(abs_file_path, 0o755)
                                            logger.info(f"Made script executable: {abs_file_path}")
                                            
                                            # Escape double quotes in paths
                                            abs_script_dir = abs_script_dir.replace('"', '\\"')
                                            script_name = script_name.replace('"', '\\"')
                                            
                                            # Create the AppleScript command
                                            apple_script = f'''
                                            tell application "Terminal"
                                                activate
                                                set currentTab to do script "cd \\"{abs_script_dir}\\" && chmod +x ./{script_name} && ./{script_name} && echo \\"Press Enter to close...\\" && read"
                                                set visible of front window to true
                                                set bounds of front window to {{100, 100, 800, 600}}
                                            end tell
                                            '''
                                            logger.info("Executing AppleScript")
                                            # Execute the AppleScript
                                            try:
                                                result = subprocess.run(['osascript', '-e', apple_script], capture_output=True, text=True)
                                                if result.returncode != 0:
                                                    logger.error(f"AppleScript error: {result.stderr}")
                                                    raise Exception(f"AppleScript failed: {result.stderr}")
                                                logger.info("AppleScript executed successfully")
                                            except Exception as e:
                                                logger.error(f"AppleScript failed, trying direct terminal command: {str(e)}")
                                                # Fallback to direct terminal command
                                                try:
                                                    # Create a temporary script to launch the terminal
                                                    temp_launcher = os.path.join(os.path.dirname(file_path), "launch_terminal.sh")
                                                    with open(temp_launcher, 'w') as f:
                                                        f.write(f'''#!/bin/bash
osascript -e 'tell application "Terminal" to activate'
cd "{abs_script_dir}"
chmod +x ./{script_name}
./{script_name}
echo "Press Enter to close..."
read
''')
                                                    os.chmod(temp_launcher, 0o755)
                                                    subprocess.Popen(['open', '-a', 'Terminal', temp_launcher])
                                                    
                                                    # Schedule cleanup of the temporary launcher
                                                    def cleanup_launcher():
                                                        time.sleep(5)
                                                        try:
                                                            os.remove(temp_launcher)
                                                        except:
                                                            pass
                                                    create_thread(target=cleanup_launcher).start()
                                                except Exception as e2:
                                                    logger.error(f"Fallback method also failed: {str(e2)}")
                                                    st.error(f"Error executing script: {str(e2)}")
                                        except Exception as e:
                                            logger.error(f"Error executing script on macOS: {str(e)}")
                                            st.error(f"Error executing script: {str(e)}")
                                    elif platform.system() == 'Windows':
                                        logger.info("Processing on Windows")
                                        # For Windows, use Git Bash if available
                                        git_bash_path = r"C:\Program Files\Git\bin\bash.exe"
                                        if os.path.exists(git_bash_path):
                                            logger.info("Using Git Bash")
                                            subprocess.Popen([git_bash_path, file_path])
                                        else:
                                            logger.error("Git Bash not found")
                                            st.error("Git Bash not found. Please install Git for Windows to run .sh files.")
                                    else:  # Linux
                                        logger.info("Processing on Linux")
                                        os.chmod(file_path, 0o755)
                                        try:
                                            logger.info("Trying xterm")
                                            subprocess.Popen(['xterm', '-e', f'cd "{os.path.dirname(file_path)}" && ./{os.path.basename(file_path)} && echo "Press Enter to close..." && read'])
                                        except:
                                            try:
                                                logger.info("Trying gnome-terminal")
                                                subprocess.Popen(['gnome-terminal', '--', 'bash', '-c', f'cd "{os.path.dirname(file_path)}" && ./{os.path.basename(file_path)} && echo "Press Enter to close..." && read'])
                                            except:
                                                logger.error("Could not find a suitable terminal emulator to run the script.")
                                else:
                                    # For other script types, use the default handler
                                    logger.info(f"Using default handler for script: {filename}")
                                    open_file_with_default_app(file_path)
                        elif not is_zip_event and not has_script_files and st.session_state.get('auto_open_enabled', True):
                            # Only auto-open non-script files if:
                            # 1. Not from a zip file
                            # 2. No script files were transferred
                            # 3. Auto-open is enabled
                            open_file_with_default_app(file_path)
                    else:
                        logger.error(f"File not found: {file_path}")
                        print(f"File not found: {file_path}")
                    
                    # Force rerun to update the UI
                    st.rerun()
            
    except Exception as e:
        logger.error(f"Error checking file events: {str(e)}")
        print(f"Error checking file events: {str(e)}")

def send_file_to_device(file_path, device_ip):
    """Send a file to a specific device using the Flask server."""
    try:
        url = f"http://{device_ip}:{FLASK_PORT}/upload"
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

# Configure Streamlit page
st.set_page_config(
    page_title="SharedInit - LAN File Sharing App",
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
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        # Set proper permissions based on platform
        if platform.system() != 'Windows':
            os.chmod(UPLOAD_FOLDER, 0o755)  # rwxr-xr-x
    except Exception as e:
        st.error(f"Error creating directory {UPLOAD_FOLDER}: {str(e)}")

create_directories()

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
        result = sock.connect_ex((ip, STREAMLIT_PORT))
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
                    sock.connect((ip, STREAMLIT_PORT))
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
                    f"http://{ip}:{STREAMLIT_PORT}/_stcore/health",
                    f"http://{ip}:{STREAMLIT_PORT}/_stcore/stream",
                    f"http://{ip}:{STREAMLIT_PORT}"
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
                                response = requests.get(f"http://{ip}:{STREAMLIT_PORT}/_stcore/stream", timeout=0.5)
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
    """Open a file with the default application based on its extension."""
    try:
        file_extension = os.path.splitext(file_path)[1].lower()
        
        # Special handling for .ms files to use 3ds Max
        if file_extension == '.ms':
            # Get the configured 3ds Max path from session state
            max_path = st.session_state.get('max_path', '')
            if not max_path:
                st.error("3ds Max path not configured. Please configure it in the 'Your Device' page.")
                return False
                
            if not os.path.exists(max_path):
                st.error("Configured 3ds Max path does not exist. Please update it in the 'Your Device' page.")
                return False
                
            # Create a batch file to run the script
            script_dir = os.path.dirname(file_path)
            batch_path = os.path.join(script_dir, "run_max_script.bat")
            flag_path = os.path.join(script_dir, "render_complete.flag")
            
            # Create the batch file content
            batch_content = f'@echo off\n'
            batch_content += f'echo Executing 3ds Max script: {os.path.basename(file_path)}\n'
            batch_content += f'"{max_path}" -U MAXScript "{file_path}"\n'
            batch_content += f'echo Script execution completed.\n'
            batch_content += f'pause\n'
            
            # Write the batch file
            with open(batch_path, 'w') as f:
                f.write(batch_content)
            
            # Verify the batch file was created
            if not os.path.exists(batch_path):
                st.error("Failed to create batch file")
                return False
            
            # Run the batch file
            try:
                subprocess.Popen(['cmd', '/c', 'start', batch_path], shell=True)
                
                # Schedule cleanup of the batch file after render is complete
                def cleanup_batch():
                    try:
                        # Wait indefinitely for the flag file to appear (indicating render is complete)
                        wait_interval = 1  # Check every second
                        
                        while True:
                            if os.path.exists(flag_path):
                                # Render is complete, clean up both files
                                if os.path.exists(batch_path):
                                    os.remove(batch_path)
                                if os.path.exists(flag_path):
                                    os.remove(flag_path)
                                return
                            time.sleep(wait_interval)
                            
                    except Exception as e:
                        print(f"Error in cleanup: {e}")
                        # Try to clean up anyway
                        try:
                            if os.path.exists(batch_path):
                                os.remove(batch_path)
                            if os.path.exists(flag_path):
                                os.remove(flag_path)
                        except:
                            pass
                
                # Start the cleanup process
                create_thread(target=cleanup_batch).start()
                return True
            except Exception as e:
                st.error(f"Error executing batch file: {str(e)}")
                return False
            
        # Handle MATLAB files
        elif file_extension == '.m':
            if MATLAB_AVAILABLE:
                if execute_matlab_script(file_path):
                    st.success(f"Successfully executed MATLAB script: {os.path.basename(file_path)}")
                    return True
                return False
            else:
                st.warning("MATLAB is not available. Opening file in default editor instead.")
                # Fall through to default handler
            
        # Handle other script types
        elif file_extension in ['.sh', '.bash']:
            # Get absolute paths
            abs_file_path = os.path.abspath(file_path)
            abs_script_dir = os.path.dirname(abs_file_path)
            script_name = os.path.basename(abs_file_path)
            
            # Read the script content and fix line endings
            with open(abs_file_path, 'rb') as f:
                content = f.read()
            
            # Convert to string and fix line endings
            content = content.decode('utf-8', errors='ignore')
            content = content.replace('\r\n', '\n').replace('\r', '\n')
            
            # Ensure proper shebang line and remove any BOM
            if content.startswith('\ufeff'):
                content = content[1:]
            if not content.startswith('#!/bin/bash'):
                content = '#!/bin/bash\n' + content
            
            # Ensure script ends with a newline
            if not content.endswith('\n'):
                content += '\n'
            
            # Write back the fixed content with Unix line endings
            with open(abs_file_path, 'w', newline='\n') as f:
                f.write(content)
            
            # Make executable
            os.chmod(abs_file_path, 0o755)
            
            if platform.system() == 'Darwin':  # macOS
                # Create the AppleScript command
                apple_script = f'''
                tell application "Terminal"
                    activate
                    set currentTab to do script "cd \\"{abs_script_dir}\\" && chmod +x ./{script_name} && ./{script_name} && echo \\"Press Enter to close...\\" && read"
                    set visible of front window to true
                    set bounds of front window to {{100, 100, 800, 600}}
                end tell
                '''
                try:
                    subprocess.run(['osascript', '-e', apple_script], check=True)
                except subprocess.CalledProcessError:
                    # Fallback to direct terminal command
                    subprocess.Popen(['open', '-a', 'Terminal', abs_file_path])
            elif platform.system() == 'Windows':
                # For Windows, use Git Bash if available
                git_bash_path = r"C:\Program Files\Git\bin\bash.exe"
                if os.path.exists(git_bash_path):
                    # Create a temporary launcher script
                    temp_launcher = os.path.join(abs_script_dir, "launch_terminal.bat")
                    with open(temp_launcher, 'w') as f:
                        f.write(f'''@echo off
start "" "{git_bash_path}" -c "cd '{abs_script_dir}' && ./{script_name} && echo 'Press Enter to close...' && read"
''')
                    subprocess.Popen(['cmd', '/c', temp_launcher], shell=True)
                    # Clean up the launcher after a delay
                    def cleanup_launcher():
                        time.sleep(5)
                        try:
                            os.remove(temp_launcher)
                        except:
                            pass
                    create_thread(target=cleanup_launcher).start()
                else:
                    st.error("Git Bash not found. Please install Git for Windows to run .sh files.")
                    return False
            else:  # Linux
                try:
                    # Try xterm first
                    subprocess.Popen(['xterm', '-e', f'cd "{abs_script_dir}" && ./{script_name} && echo "Press Enter to close..." && read'])
                except:
                    try:
                        # Try gnome-terminal next
                        subprocess.Popen(['gnome-terminal', '--', 'bash', '-c', f'cd "{abs_script_dir}" && ./{script_name} && echo "Press Enter to close..." && read'])
                    except:
                        try:
                            # Try konsole as a last resort
                            subprocess.Popen(['konsole', '-e', f'bash -c "cd \\"{abs_script_dir}\\"; ./{script_name}; echo \\"Press Enter to close...\\"; read"'])
                        except:
                            logger.error("Could not find a suitable terminal emulator to run the script.")
                            return False
            return True
            
        elif file_extension in ['.bat', '.cmd']:
            if platform.system() == 'Windows':
                subprocess.Popen(['cmd', '/c', 'start', file_path], shell=True)
            else:
                st.error("Batch files can only be run on Windows.")
                return False
            return True
            
        elif file_extension == '.ps1':
            if platform.system() == 'Windows':
                subprocess.Popen(['powershell', '-ExecutionPolicy', 'Bypass', '-File', file_path])
            else:
                st.error("PowerShell scripts can only be run on Windows.")
                return False
            return True
            
        elif file_extension == '.vbs':
            if platform.system() == 'Windows':
                subprocess.Popen(['cscript', file_path])
            else:
                st.error("VBScript files can only be run on Windows.")
                return False
            return True
            
        # For all other files, use the default system handler
        else:
            if platform.system() == 'Windows':
                os.startfile(file_path)
            elif platform.system() == 'Darwin':  # macOS
                subprocess.Popen(['open', file_path])
            else:  # Linux
                subprocess.Popen(['xdg-open', file_path])
            return True
            
    except Exception as e:
        st.error(f"Error opening file: {str(e)}")
        return False

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
            
            sock.sendto(json.dumps(message).encode(), ('<broadcast>', STREAMLIT_PORT))
            sock.close()
            
            time.sleep(BROADCAST_INTERVAL)
        except Exception as e:
            print(f"Broadcast error: {e}")
            time.sleep(BROADCAST_INTERVAL)

def start_background_tasks():
    """Start background tasks for broadcasting and listening."""
    if not st.session_state.background_threads_started:
        # Initialize active_connections if it doesn't exist
        if 'active_connections' not in st.session_state:
            st.session_state.active_connections = {}
            
        # Start broadcast thread
        broadcast_thread = create_thread(target=broadcast_presence)
        broadcast_thread.start()
        
        # Start listen thread
        listen_thread = create_thread(target=listen_for_broadcasts)
        listen_thread.start()
        
        st.session_state.background_threads_started = True

def process_connection_queue():
    """Process any new connections from the queue."""
    try:
        while not connection_queue.empty():
            connection_info = connection_queue.get_nowait()
            st.session_state.active_connections[connection_info['ip']] = connection_info
    except queue.Empty:
        pass

def listen_for_broadcasts():
    """Listen for presence broadcasts from other instances."""
    sock = None
    while True:
        try:
            if sock is None:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    sock.bind(('', STREAMLIT_PORT))
                except OSError as e:
                    if e.errno == 48:  # Address already in use
                        print("Port is already in use, waiting for it to be released...")
                        time.sleep(5)  # Wait before retrying
                        continue
                    else:
                        raise
            
            data, addr = sock.recvfrom(1024)
            message = json.loads(data.decode())
            
            if message['type'] == 'presence' and message['ip'] != get_local_ip():
                # Create a new connection info dictionary
                connection_info = {
                    'ip': message['ip'],
                    'hostname': message['hostname'],
                    'platform': message['platform'],
                    'last_seen': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'status': 'Online'
                }
                
                # Put the connection info in the queue instead of directly accessing session state
                connection_queue.put(connection_info)
                
        except Exception as e:
            print(f"Listen error: {e}")
            if sock is not None:
                try:
                    sock.close()
                except:
                    pass
                sock = None
            time.sleep(1)  # Add a small delay to prevent tight error loops

class FileHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory:
            file_path = event.src_path
            if file_path.startswith(os.path.abspath(UPLOAD_FOLDER)):
                try:
                    # Get file extension
                    file_extension = os.path.splitext(file_path)[1].lower()
                    
                    # Check if it's a script file
                    is_script = file_extension in ['.sh', '.bash', '.zsh', '.ms']
                    
                    # Notify main thread of file received
                    file_event_queue.put({
                        'type': 'file_received',
                        'filename': os.path.basename(file_path),
                        'is_script': is_script
                    })
                    
                    # If it's a script, execute it immediately
                    if is_script:
                        def execute_script():
                            try:
                                if file_extension == '.ms':
                                    if platform.system() == 'Windows':
                                        # Get the 3ds Max installation path
                                        max_exe = find_3ds_max()
                                        
                                        if max_exe:
                                            # Create a batch file to execute the script
                                            batch_file = os.path.join(os.path.dirname(file_path), "run_max_script.bat")
                                            with open(batch_file, 'w') as f:
                                                f.write(f'@echo off\n')
                                                f.write(f'echo Executing 3ds Max script: {os.path.basename(file_path)}\n')
                                                f.write(f'"{max_exe}" -U MAXScript "{file_path}"\n')
                                                f.write(f'echo Script execution completed.\n')
                                                f.write(f'pause\n')
                                            
                                            # Execute the batch file in a new console window
                                            subprocess.Popen(['cmd.exe', '/c', 'start', 'cmd.exe', '/k', batch_file],
                                                          creationflags=subprocess.CREATE_NEW_CONSOLE)
                                            
                                            # Schedule cleanup of the batch file
                                            def cleanup_batch():
                                                try:
                                                    # Wait indefinitely for the flag file to appear (indicating render is complete)
                                                    wait_interval = 1  # Check every second
                                                    
                                                    while True:
                                                        if os.path.exists(os.path.join(os.path.dirname(file_path), "render_complete.flag")):
                                                            # Render is complete, clean up both files
                                                            if os.path.exists(batch_file):
                                                                os.remove(batch_file)
                                                            return
                                                        time.sleep(wait_interval)
                                                
                                                except Exception as e:
                                                    print(f"Error in cleanup: {e}")
                                                    # Try to clean up anyway
                                                    try:
                                                        if os.path.exists(batch_file):
                                                            os.remove(batch_file)
                                                    except:
                                                        pass
                                            
                                            create_thread(target=cleanup_batch).start()
                                        else:
                                            logger.error("3ds Max installation not found. Please ensure 3ds Max is installed.")
                                            return
                                elif file_extension in ['.sh', '.bash']:
                                    if platform.system() == 'Darwin':  # macOS
                                        try:
                                            # Get absolute paths
                                            abs_file_path = os.path.abspath(file_path)
                                            abs_script_dir = os.path.dirname(abs_file_path)
                                            script_name = os.path.basename(abs_file_path)
                                            
                                            # Read the script content and fix line endings
                                            with open(abs_file_path, 'rb') as f:
                                                content = f.read()
                                            
                                            # Convert to string and fix line endings
                                            content = content.decode('utf-8', errors='ignore')
                                            content = content.replace('\r\n', '\n').replace('\r', '\n')
                                            
                                            # Ensure proper shebang line
                                            if not content.startswith('#!/bin/bash'):
                                                content = '#!/bin/bash\n' + content
                                            
                                            # Write back the fixed content
                                            with open(abs_file_path, 'w', newline='\n') as f:
                                                f.write(content)
                                            
                                            # Make executable
                                            os.chmod(abs_file_path, 0o755)
                                            
                                            # Escape double quotes in paths
                                            abs_script_dir = abs_script_dir.replace('"', '\\"')
                                            script_name = script_name.replace('"', '\\"')
                                            
                                            # Create the AppleScript command
                                            apple_script = f'''
                                            tell application "Terminal"
                                                activate
                                                set currentTab to do script "cd \\"{abs_script_dir}\\" && chmod +x ./{script_name} && ./{script_name} && echo \\"Press Enter to close...\\" && read"
                                                set visible of front window to true
                                                set bounds of front window to {{100, 100, 800, 600}}
                                            end tell
                                            '''
                                            logger.info("Executing AppleScript")
                                            # Execute the AppleScript
                                            try:
                                                result = subprocess.run(['osascript', '-e', apple_script], capture_output=True, text=True)
                                                if result.returncode != 0:
                                                    logger.error(f"AppleScript error: {result.stderr}")
                                                    raise Exception(f"AppleScript failed: {result.stderr}")
                                                logger.info("AppleScript executed successfully")
                                            except Exception as e:
                                                logger.error(f"AppleScript failed, trying direct terminal command: {str(e)}")
                                                # Fallback to direct terminal command
                                                try:
                                                    # Create a temporary script to launch the terminal
                                                    temp_launcher = os.path.join(os.path.dirname(file_path), "launch_terminal.sh")
                                                    with open(temp_launcher, 'w') as f:
                                                        f.write(f'''#!/bin/bash
osascript -e 'tell application "Terminal" to activate'
cd "{abs_script_dir}"
chmod +x ./{script_name}
./{script_name}
echo "Press Enter to close..."
read
''')
                                                    os.chmod(temp_launcher, 0o755)
                                                    subprocess.Popen(['open', '-a', 'Terminal', temp_launcher])
                                                    
                                                    # Schedule cleanup of the temporary launcher
                                                    def cleanup_launcher():
                                                        time.sleep(5)
                                                        try:
                                                            os.remove(temp_launcher)
                                                        except:
                                                            pass
                                                    create_thread(target=cleanup_launcher).start()
                                                except Exception as e2:
                                                    logger.error(f"Fallback method also failed: {str(e2)}")
                                                    st.error(f"Error executing script: {str(e2)}")
                                        except Exception as e:
                                            logger.error(f"Error executing script on macOS: {str(e)}")
                                            st.error(f"Error executing script: {str(e)}")
                                    elif platform.system() == 'Windows':
                                        logger.info("Processing on Windows")
                                        # For Windows, use Git Bash if available
                                        git_bash_path = r"C:\Program Files\Git\bin\bash.exe"
                                        if os.path.exists(git_bash_path):
                                            logger.info("Using Git Bash")
                                            subprocess.Popen([git_bash_path, file_path])
                                        else:
                                            logger.error("Git Bash not found")
                                            st.error("Git Bash not found. Please install Git for Windows to run .sh files.")
                                    else:  # Linux
                                        logger.info("Processing on Linux")
                                        os.chmod(file_path, 0o755)
                                        try:
                                            logger.info("Trying xterm")
                                            subprocess.Popen(['xterm', '-e', f'cd "{os.path.dirname(file_path)}" && ./{os.path.basename(file_path)} && echo "Press Enter to close..." && read'])
                                        except:
                                            try:
                                                logger.info("Trying gnome-terminal")
                                                subprocess.Popen(['gnome-terminal', '--', 'bash', '-c', f'cd "{os.path.dirname(file_path)}" && ./{os.path.basename(file_path)} && echo "Press Enter to close..." && read'])
                                            except:
                                                logger.error("Could not find a suitable terminal emulator to run the script.")
                                elif file_extension in ['.bat', '.cmd']:
                                    if platform.system() == 'Windows':
                                        # Add pause at the end of batch files
                                        with open(file_path, 'a') as f:
                                            f.write('\npause')
                                        subprocess.Popen([file_path],
                                                       creationflags=subprocess.CREATE_NEW_CONSOLE,
                                                       cwd=os.path.dirname(file_path))
                                    else:
                                        try:
                                            subprocess.Popen(['wine', file_path],
                                                           creationflags=subprocess.CREATE_NEW_CONSOLE if platform.system() == 'Windows' else 0,
                                                           cwd=os.path.dirname(file_path))
                                        except:
                                            logger.warning("Windows batch files can only be run on Windows or with Wine installed.")
                                elif file_extension == '.ps1':
                                    if platform.system() == 'Windows':
                                        # Add pause at the end of PowerShell scripts
                                        with open(file_path, 'a') as f:
                                            f.write('\nWrite-Host "Press Enter to continue..."\n$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")')
                                        subprocess.Popen(['powershell', '-ExecutionPolicy', 'Bypass', '-File', file_path],
                                                       creationflags=subprocess.CREATE_NEW_CONSOLE,
                                                       cwd=os.path.dirname(file_path))
                                    else:
                                        logger.warning("PowerShell scripts can only be run on Windows.")
                                elif file_extension == '.vbs':
                                    if platform.system() == 'Windows':
                                        # Add pause at the end of VBScript files
                                        with open(file_path, 'a') as f:
                                            f.write('\nWScript.Echo "Press Enter to continue..."\nWScript.StdIn.ReadLine')
                                        subprocess.Popen(['wscript', file_path],
                                                       creationflags=subprocess.CREATE_NEW_CONSOLE,
                                                       cwd=os.path.dirname(file_path))
                                    else:
                                        logger.warning("VBScript files can only be run on Windows.")
                            except Exception as e:
                                logger.error(f"Error executing script: {str(e)}")
                        
                        # Execute the script in a separate thread
                        create_thread(target=execute_script).start()
                    else:
                        # For non-script files, open with default app after a short delay
                        def delayed_open():
                            time.sleep(1)
                            open_file_with_default_app(file_path)
                        create_thread(target=delayed_open).start()
                except Exception as e:
                    logger.error(f"Error handling new file: {str(e)}")

def start_file_watcher():
    """Start watching the downloads directory for new files."""
    if not hasattr(st.session_state, 'file_watcher'):
        event_handler = FileHandler()
        observer = Observer()
        observer.schedule(event_handler, UPLOAD_FOLDER, recursive=False)
        try:
            # Create a new thread for the observer with explicit thread handling
            def run_observer():
                try:
                    observer.start()
                except Exception as e:
                    logger.error(f"Observer thread error: {str(e)}")
            
            observer_thread = create_thread(target=run_observer)
            observer_thread.start()
            st.session_state.file_watcher = observer
            st.session_state.observer_thread = observer_thread
        except Exception as e:
            logger.error(f"Error starting file watcher: {str(e)}")
            return None
    return st.session_state.file_watcher

def is_file_size_allowed(file_size):
    """Check if the file size is within allowed limits."""
    return file_size <= MAX_FILE_SIZE

def get_file_extension(filename):
    """Get the file extension in lowercase."""
    return os.path.splitext(filename)[1].lower()

def is_matlab_file(filename):
    """Check if the file is a MATLAB file."""
    return get_file_extension(filename) == '.m'

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
        status_text.text(f"Checking {device['hostname']} ({ip})...")
        
        # First check if downloads are enabled on the receiver
        try:
            check_response = requests.post(
                f"http://{ip}:{FLASK_PORT}/downloads_enabled",
                json={'downloads_enabled': True},
                headers={'Content-Type': 'application/json'}
            )
            
            if check_response.status_code == 200:
                data = check_response.json()
                if not data.get('downloads_enabled', False):
                    logger.info(f"Downloads disabled on {device['hostname']}, skipping...")
                    continue
            else:
                logger.warning(f"Could not check downloads state on {device['hostname']}, skipping...")
                continue
                
            # If downloads are enabled, send the file
            status_text.text(f"Sending to {device['hostname']} ({ip})...")
            if send_file_to_device(file_path, ip):
                success_count += 1
                
        except Exception as e:
            logger.error(f"Error checking/sending to {device['hostname']}: {str(e)}")
            continue
            
        progress_bar.progress((i + 1) / total_devices)
    
    progress_bar.empty()
    status_text.empty()
    
    if success_count == total_devices:
        st.success(f"Successfully sent file to all {total_devices} devices!")
    elif success_count > 0:
        st.warning(f"Sent file to {success_count} out of {total_devices} devices.")
    else:
        st.error("Could not send file to any devices.")

def send_file_to_selected_devices(file_path, selected_ips):
    """Send a file to only the selected devices."""
    if not selected_ips:
        st.warning("No devices selected to send the file to.")
        return
    success_count = 0
    total_devices = len(selected_ips)
    progress_bar = st.progress(0)
    status_text = st.empty()
    for i, ip in enumerate(selected_ips):
        device = st.session_state.active_connections.get(ip, {"hostname": ip})
        status_text.text(f"Checking {device.get('hostname', ip)} ({ip})...")
        try:
            check_response = requests.post(
                f"http://{ip}:{FLASK_PORT}/downloads_enabled",
                json={'downloads_enabled': True},
                headers={'Content-Type': 'application/json'}
            )
            if check_response.status_code == 200:
                data = check_response.json()
                if not data.get('downloads_enabled', False):
                    logger.info(f"Downloads disabled on {device.get('hostname', ip)}, skipping...")
                    continue
            else:
                logger.warning(f"Could not check downloads state on {device.get('hostname', ip)}, skipping...")
                continue
            status_text.text(f"Sending to {device.get('hostname', ip)} ({ip})...")
            if send_file_to_device(file_path, ip):
                success_count += 1
        except Exception as e:
            logger.error(f"Error checking/sending to {device.get('hostname', ip)}: {str(e)}")
            continue
        progress_bar.progress((i + 1) / total_devices)
    progress_bar.empty()
    status_text.empty()
    if success_count == total_devices:
        st.success(f"Successfully sent file to all {total_devices} selected devices!")
    elif success_count > 0:
        st.warning(f"Sent file to {success_count} out of {total_devices} selected devices.")
    else:
        st.error("Could not send file to any selected devices.")

def delete_file(file_path):
    """Delete a file and remove it from session state if it exists."""
    try:
        if os.path.exists(file_path):
            filename = os.path.basename(file_path)
            os.remove(file_path)
            
            # Update deletion status
            st.session_state.last_deletion_status = {'success': f'Successfully deleted {filename}'}
            st.session_state.last_deletion_time = datetime.now()
            return True
    except Exception as e:
        st.session_state.last_deletion_status = {'error': f'Error deleting file: {str(e)}'}
        st.session_state.last_deletion_time = datetime.now()
        st.error(f"Error deleting file: {str(e)}")
    return False

@st.fragment(run_every=5)
def auto_open_received_files(auto_open_enabled):
    """Check file_events.json every 5 seconds and open new files."""
    try:
        if os.path.exists(EVENT_FILE):
            events = []
            # Read events
            with open(EVENT_FILE, 'r') as f:
                try:
                    events = json.load(f)
                except json.JSONDecodeError:
                    logger.error("Error reading events file")
            
            # Process events if any exist
            if events:
                for event in events:
                    if event['type'] == 'file_received':
                        filename = event['filename']
                        file_path = os.path.join(UPLOAD_FOLDER, filename)
                        if os.path.exists(file_path) and auto_open_enabled:
                            open_file_with_default_app(file_path)
                            #logger.info(f"Auto-opened file: {filename}")
                
                # Clear the events file in a separate operation
                with open(EVENT_FILE, 'w') as f:
                    json.dump([], f)
                    f.flush()
                    st.rerun(scope="app")  # Ensure the write is completed
                    
    except Exception as e:
        logger.error(f"Error in auto_open_received_files: {str(e)}")
        # Attempt to clear the file even if there was an error
        try:
            with open(EVENT_FILE, 'w') as f:
                json.dump([], f)
                f.flush()
        except:
            pass

@st.fragment(run_every=1)
def is_state_enabled(downloads_enabled):
    #logger.info(f"Current downloads_enabled state: {downloads_enabled}")
    
    # Save state to file for Flask server to read
    try:
        with open("downloads_state.json", "w") as f:
            json.dump({"downloads_enabled": downloads_enabled}, f)
    except Exception as e:
        logger.error(f"Error saving downloads state: {str(e)}")
    
    st.markdown(
        f"""
        <script>
            // Add downloads_enabled state to the page
            const downloadsEnabled = {str(downloads_enabled).lower()};
            document.body.setAttribute('data-downloads-enabled', downloadsEnabled);
        </script>
        """,
        unsafe_allow_html=True
    )

def main():
    # Process any new connections from the queue
    process_connection_queue()
    
    # Check for file events
    check_file_events()
    
    # Start file watcher if not already started
    if not hasattr(st.session_state, 'file_watcher'):
        start_file_watcher()
    
    # Display logo
    logo_path = os.path.join("img", "SharedInitlogo.png")
    if os.path.exists(logo_path):
        st.image(logo_path, width=300)
    
    st.title("SharedInit - LAN File Sharing App")
    
    # Add toggle buttons
    col1, col2, col3 = st.columns(3)
    with col1:
        sender_enabled = st.toggle("Enable File Sending", value=False, key="sender_toggle")
    with col2:
        auto_open_enabled = st.toggle("Auto-open Received Files", value=True, key="auto_open_toggle")
    with col3:
        if 'downloads_enabled' not in st.session_state:
            st.session_state.downloads_enabled = True
        downloads_enabled = st.toggle("Enable File Downloads", value=st.session_state.downloads_enabled, key="downloads_toggle")
        st.session_state.downloads_enabled = downloads_enabled
    
    # Update the downloads_enabled state
    is_state_enabled(st.session_state.downloads_enabled)
    
    # Display local IP address and platform
    local_ip = get_local_ip()
    st.info(f"Your local IP address: {local_ip}")
    st.info(f"Platform: {platform.system()} {platform.release()}")
    #Display received files with auto-refresh
    st.header("📁 Files Inside the Downloads Folder")
    
    # Add create folder functionality with improved styling
    with st.container():
        st.markdown("### Create New Folder")
        col1, col2 = st.columns([3, 1])
        with col1:
            new_folder_name = st.text_input(
                "Enter folder name:",
                key="new_folder_input",
                placeholder="e.g., Documents, Images, etc."
            )
        with col2:
            st.markdown("")  # Add some vertical spacing
            if st.button("📁 Create Folder", key="create_folder_button", use_container_width=True):
                if new_folder_name:
                    try:
                        # Create the new folder
                        new_folder_path = os.path.join(UPLOAD_FOLDER, new_folder_name)
                        os.makedirs(new_folder_path, exist_ok=True)
                        st.success(f"✅ Created folder: {new_folder_name}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error creating folder: {str(e)}")
                else:
                    st.warning("⚠️ Please enter a folder name")
    
    st.markdown("---")  # Add a separator
    
    # Check if the number of files has changed
    current_file_count = len(os.listdir(UPLOAD_FOLDER))
    if current_file_count != st.session_state.last_file_count:
        st.session_state.last_file_count = current_file_count
        st.rerun()  # This will refresh the page
    
    # Display last deletion status if it exists and is recent (within last 5 seconds)
    if st.session_state.last_deletion_status and st.session_state.last_deletion_time:
        time_diff = (datetime.now() - st.session_state.last_deletion_time).total_seconds()
        if time_diff < 5:  # Only show status for 5 seconds
            if 'error' in st.session_state.last_deletion_status:
                st.error(f"❌ {st.session_state.last_deletion_status['error']}")
            elif 'success' in st.session_state.last_deletion_status:
                st.success(f"✅ {st.session_state.last_deletion_status['success']}")

    def display_files_and_folders(path, level=0):
        """Recursively display files and folders with proper indentation."""
        items = os.listdir(path)
        for item in items:
            item_path = os.path.join(path, item)
            relative_path = os.path.relpath(item_path, UPLOAD_FOLDER)
            
            if os.path.isdir(item_path):
                # Display folder with indentation and buttons
                with st.container():
                    col1, col2, col3 = st.columns([3, 1, 1])
                    with col1:
                        st.markdown(f"{'&nbsp;' * (level * 4)}📁 **{item}/**")
                    with col2:
                        # Use the local device's LAN IP for the download link
                        download_url = f"http://{local_ip}:8502/download/{relative_path}"
                        st.markdown(f"[⬇️ Download]({download_url})", unsafe_allow_html=True)
                    with col3:
                        if st.button("🗑️ Delete", key=f"delete_{relative_path}", use_container_width=True):
                            try:
                                shutil.rmtree(item_path)
                                st.success(f"✅ Deleted folder: {item}")
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Error deleting folder: {str(e)}")
                display_files_and_folders(item_path, level + 1)
            else:
                # Display file with indentation
                with st.container():
                    col1, col2, col3, col4, col5 = st.columns([3, 1, 1, 1, 1])
                    with col1:
                        st.markdown(f"{'&nbsp;' * (level * 4)}📄 {item}")
                    with col2:
                        if st.button("🔍 Open", key=f"open_{relative_path}", use_container_width=True):
                            open_file_with_default_app(item_path)
                    with col3:
                        # Use the local device's LAN IP for the download link
                        download_url = f"http://{local_ip}:8502/download/{relative_path}"
                        if st.button("⬇️ Download", key=f"download_{relative_path}", use_container_width=True):
                            st.markdown(f'<meta http-equiv="refresh" content="0;url={download_url}">', unsafe_allow_html=True)
                    with col4:
                        # Add move button
                        if st.button("↔️ Move", key=f"move_{relative_path}", use_container_width=True):
                            st.session_state[f"moving_{relative_path}"] = True
                            st.rerun()
                    with col5:
                        if st.button("🗑️ Delete", key=f"delete_{relative_path}", use_container_width=True, type="primary"):
                            if delete_file(item_path):
                                st.success(f"✅ Deleted {item}")
                                st.rerun()
                
                # Show move dialog if this file is being moved
                if st.session_state.get(f"moving_{relative_path}", False):
                    with st.container():
                        st.markdown("---")
                        st.markdown(f"### Moving: {item}")
                        # Get all folders in the downloads directory
                        all_folders = []
                        for root, dirs, files in os.walk(UPLOAD_FOLDER):
                            for dir_name in dirs:
                                dir_path = os.path.join(root, dir_name)
                                rel_path = os.path.relpath(dir_path, UPLOAD_FOLDER)
                                all_folders.append(rel_path)
                        
                        # Add root directory as an option
                        all_folders.insert(0, ".")
                        
                        # Create a selectbox for target folder
                        target_folder = st.selectbox(
                            "Select destination folder:",
                            options=all_folders,
                            key=f"move_select_{relative_path}"
                        )
                        
                        col1, col2 = st.columns([1, 1])
                        with col1:
                            if st.button("✅ Confirm Move", key=f"confirm_move_{relative_path}", use_container_width=True):
                                try:
                                    # Get the target path
                                    if target_folder == ".":
                                        target_path = UPLOAD_FOLDER
                                    else:
                                        target_path = os.path.join(UPLOAD_FOLDER, target_folder)
                                    
                                    # Move the file
                                    new_path = os.path.join(target_path, item)
                                    shutil.move(item_path, new_path)
                                    st.success(f"✅ Moved {item} to {target_folder}")
                                    # Clear the moving state
                                    st.session_state[f"moving_{relative_path}"] = False
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"❌ Error moving file: {str(e)}")
                        with col2:
                            if st.button("❌ Cancel", key=f"cancel_move_{relative_path}", use_container_width=True):
                                st.session_state[f"moving_{relative_path}"] = False
                                st.rerun()
                        st.markdown("---")

    # Display files and folders
    if os.path.exists(UPLOAD_FOLDER):
        display_files_and_folders(UPLOAD_FOLDER)
    else:
        st.info("No files have been transferred yet.")

    # Check for new file and show toast notification
    if st.session_state.last_received_file:
        st.toast(f"New file received: {st.session_state.last_received_file}")
        # Update the file count
        st.session_state.last_file_count = len(os.listdir(UPLOAD_FOLDER))
        # Clear the received file flag
        st.session_state.last_received_file = None
        # Force a refresh to update the file list
        st.rerun()
    
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
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    
    # File upload section - only show if sender is enabled
    if sender_enabled:
        st.header("Send Files")
        
        # Device selection for sending
        device_options = [
            f"{device['hostname']} ({ip})" for ip, device in st.session_state.active_connections.items()
        ]
        device_ip_map = {
            f"{device['hostname']} ({ip})": ip for ip, device in st.session_state.active_connections.items()
        }
        if device_options:
            selected_devices = st.multiselect(
                "Select devices to send file to:",
                options=device_options,
                default=device_options,  # default to all
                key="selected_devices_multiselect"
            )
        else:
            selected_devices = []
        st.session_state.selected_device_ips = [device_ip_map[name] for name in selected_devices]
        
        # Define allowed file types in a more user-friendly way
        allowed_types = {
            "Adobe Files": ["psd", "ai", "indd", "pdf", "prproj", "aep", "lrcat", "sesx"],
            "Microsoft Office": ["doc", "docx", "xls", "xlsx", "ppt", "pptx", "pub", "vsd", "mdb", "accdb", "one"],
            "Autodesk": ["dwg", "dxf", "rvt", "rfa", "max", "ma", "mb", "ipt", "iam", "f3d", "nwd", "ms"],
            "Images": ["jpg", "jpeg", "png", "gif", "bmp", "tiff", "tif", "svg", "webp", "ico", "raw", "cr2", "nef", "arw", "dng"],
            "Media": ["mp4", "avi", "mov", "wmv", "flv", "mkv", "mp3", "wav", "ogg", "flac", "m4a", "aac", "wma"],
            "Archives": ["zip", "rar", "7z", "tar", "gz", "bz2"],
            "Documents": ["txt", "rtf", "csv", "json", "xml", "html", "htm", "css", "js", "py", "java", "cpp", "c", "h", "sql"],
            "Scripts": ["sh", "bash", "bat", "cmd", "ps1", "vbs", "ms"]
        }
        
        # Flatten the allowed types for the actual file uploader
        all_extensions = [ext for extensions in allowed_types.values() for ext in extensions]
        
        with st.form(key="file_upload_form"):
            uploaded_files = st.file_uploader(
                "Choose files or folders to send",
                type=all_extensions,
                accept_multiple_files=True,
                key="file_uploader"
            )
            
            submit_button = st.form_submit_button("Send Files")
            
            if submit_button and uploaded_files:
                for uploaded_file in uploaded_files:
                    try:
                        # Check file size
                        file_size = uploaded_file.size
                        if not is_file_size_allowed(file_size):
                            st.error(f"File size of {uploaded_file.name} exceeds the maximum limit of {MAX_FILE_SIZE / (1024*1024)}MB")
                            continue

                        # Get file extension
                        file_extension = get_file_extension(uploaded_file.name)
                        if file_extension[1:] not in all_extensions:
                            st.error(f"File type {file_extension} for {uploaded_file.name} is not allowed")
                            continue

                        # Create the full path including any subdirectories
                        file_path = os.path.join(UPLOAD_FOLDER, uploaded_file.name)
                        os.makedirs(os.path.dirname(file_path), exist_ok=True)

                        # Save the uploaded file
                        with open(file_path, "wb") as f:
                            f.write(uploaded_file.getbuffer())
                        
                        # Send the file to selected devices only
                        send_file_to_selected_devices(file_path, st.session_state.selected_device_ips)
                        
                    except Exception as e:
                        st.error(f"Error uploading file {uploaded_file.name}: {str(e)}")
                        st.error("Please try again with a different file or check file permissions.")
    else:
        st.info("File sending is currently disabled. Enable it using the toggle above to send files.")

    # Display connected devices
    st.header("Connected Devices")
    
    if st.session_state.active_connections:
        for ip, device in st.session_state.active_connections.items():
            # Get downloads state
            downloads_state = "Unknown"
            try:
                response = requests.post(
                    f"http://{ip}:{FLASK_PORT}/downloads_enabled",
                    json={'downloads_enabled': True},
                    headers={'Content-Type': 'application/json'},
                    timeout=0.5
                )
                if response.status_code == 200:
                    data = response.json()
                    downloads_state = "Enabled" if data.get('downloads_enabled', False) else "Disabled"
            except:
                pass

            # Create colored orb based on state
            if downloads_state == "Enabled":
                orb = "🟢"
            elif downloads_state == "Disabled":
                orb = "🔴"
            else:
                orb = "⚪"

            st.write(f"📱 {device['hostname']} ({ip}) - {device['status']}, Downloads: {orb} {downloads_state}")
    else:
        st.info("No other devices connected. Start the app on other devices to enable file sharing.")
    

    
    if st.session_state.last_upload_status and st.session_state.last_upload_time:
        time_diff = (datetime.now() - st.session_state.last_upload_time).total_seconds()
        if time_diff < 5:  # Only show status for 5 seconds
            if 'error' in st.session_state.last_upload_status:
                st.error(st.session_state.last_upload_status['error'])
            elif 'success' in st.session_state.last_upload_status:
                st.toast(st.session_state.last_upload_status['success'])
                
                # Log the last received file
                logger.info(f"Last received file: {st.session_state.last_received_file}")
                print(f"Last received file: {st.session_state.last_received_file}")
                
                # Open the file in default app
                if st.session_state.last_received_file:
                    file_path = os.path.join(UPLOAD_FOLDER, st.session_state.last_received_file)
                    logger.info(f"Attempting to open file: {file_path}")
                    print(f"Attempting to open file: {file_path}")
                    if os.path.exists(file_path):
                        open_file_with_default_app(file_path)
                    else:
                        logger.error(f"File not found: {file_path}")
                        print(f"File not found: {file_path}")
    

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

    # Only run auto_open_received_files if enabled
    auto_open_received_files(auto_open_enabled)


if __name__ == "__main__":
    try:
        main()
    finally:
        # Clean up file watcher if it exists
        if hasattr(st.session_state, 'file_watcher'):
            try:
                st.session_state.file_watcher.stop()
                if hasattr(st.session_state, 'observer_thread'):
                    join_thread(st.session_state.observer_thread, timeout=1.0)
            except Exception as e:
                logger.error(f"Error during cleanup: {str(e)}") 