import streamlit as st
import socket
import platform
from datetime import datetime
import os
import json
import shutil
import subprocess
import requests

# Constants
PORT = 8501  # Streamlit default port
FLASK_PORT = 8502  # Flask server port
CONFIG_FILE = "app_config.json"

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

def load_config():
    """Load configuration from file."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except:
            return {"download_folder": "downloads", "max_path": ""}
    return {"download_folder": "downloads", "max_path": ""}

def save_config(config):
    """Save configuration to file."""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f)

def change_download_folder(new_folder):
    """Change the download folder."""
    try:
        # Create new folder if it doesn't exist
        os.makedirs(new_folder, exist_ok=True)
        
        # Update session state and config
        st.session_state.download_folder = new_folder
        config = load_config()
        config["download_folder"] = new_folder
        save_config(config)
        
        # Notify Flask server about the configuration change
        try:
            response = requests.post(
                f"http://localhost:{FLASK_PORT}/update_config",
                json={"download_folder": new_folder},
                timeout=1
            )
            if response.status_code != 200:
                st.warning("Flask server was notified but returned an error. Some features may not work until you restart the app.")
        except Exception as e:
            st.warning("Could not notify Flask server about the configuration change. Some features may not work until you restart the app.")
        
        return True
    except Exception as e:
        st.error(f"Error changing download folder: {str(e)}")
        return False

def change_max_path(new_path):
    """Change the 3ds Max installation path."""
    try:
        if not new_path:
            st.error("Please select the 3dsmax.exe file")
            return False
            
        if not os.path.exists(new_path):
            st.error("The selected file does not exist")
            return False
            
        if os.path.basename(new_path).lower() != "3dsmax.exe":
            st.error("Please select the 3dsmax.exe file")
            return False
        
        # Update session state and config
        st.session_state.max_path = new_path
        config = load_config()
        config["max_path"] = new_path
        save_config(config)
        
        # Notify Flask server about the configuration change
        try:
            response = requests.post(
                f"http://localhost:{FLASK_PORT}/update_config",
                json={"max_path": new_path},
                timeout=1
            )
            if response.status_code != 200:
                st.warning("Flask server was notified but returned an error. Some features may not work until you restart the app.")
        except Exception as e:
            st.warning("Could not notify Flask server about the configuration change. Some features may not work until you restart the app.")
        
        return True
    except Exception as e:
        st.error(f"Error changing 3ds Max path: {str(e)}")
        return False

def open_folder_picker():
    """Open a folder picker dialog based on the operating system."""
    if platform.system() == 'Darwin':  # macOS
        try:
            # Use osascript to show a folder picker dialog
            script = '''
            tell application "System Events"
                activate
                set folderPath to choose folder with prompt "Select Download Folder"
                return POSIX path of folderPath
            end tell
            '''
            folder_path = subprocess.check_output(['osascript', '-e', script]).decode().strip()
            return folder_path
        except Exception as e:
            st.error(f"Error opening folder picker: {str(e)}")
            return None
    elif platform.system() == 'Windows':  # Windows
        try:
            # Use PowerShell command to show folder picker dialog
            powershell_command = '''
            Add-Type -AssemblyName System.Windows.Forms
            $folderBrowser = New-Object System.Windows.Forms.FolderBrowserDialog
            $folderBrowser.Description = "Select Download Folder"
            $folderBrowser.RootFolder = "MyComputer"
            if ($folderBrowser.ShowDialog() -eq "OK") {
                $folderBrowser.SelectedPath
            }
            '''
            result = subprocess.run(
                ["powershell", "-Command", powershell_command],
                capture_output=True,
                text=True
            )
            if result.returncode == 0 and result.stdout.strip():
                return os.path.normpath(result.stdout.strip())
            return None
        except Exception as e:
            st.error(f"Error opening folder picker: {str(e)}")
            return None
    else:
        return None  # For other platforms, we'll use manual input

def open_file_picker():
    """Open a file picker dialog for 3dsmax.exe."""
    if platform.system() == 'Windows':
        try:
            # Use PowerShell command to show file picker dialog
            powershell_command = '''
            Add-Type -AssemblyName System.Windows.Forms
            $fileBrowser = New-Object System.Windows.Forms.OpenFileDialog
            $fileBrowser.Title = "Select 3dsmax.exe"
            $fileBrowser.Filter = "3ds Max Executable (3dsmax.exe)|3dsmax.exe"
            $fileBrowser.InitialDirectory = "C:\\"
            $fileBrowser.FileName = "3dsmax.exe"
            if ($fileBrowser.ShowDialog() -eq "OK") {
                $fileBrowser.FileName
            }
            '''
            result = subprocess.run(
                ["powershell", "-Command", powershell_command],
                capture_output=True,
                text=True
            )
            if result.returncode == 0 and result.stdout.strip():
                selected_path = os.path.normpath(result.stdout.strip())
                # Validate that it's actually 3dsmax.exe
                if os.path.basename(selected_path).lower() == "3dsmax.exe":
                    return selected_path
                else:
                    st.error("Please select the 3dsmax.exe file")
                    return None
            return None
        except Exception as e:
            st.error(f"Error opening file picker: {str(e)}")
            return None
    else:
        return None

def main():
    st.title("Your Device")
    
    # Load configuration
    config = load_config()
    if 'download_folder' not in st.session_state:
        st.session_state.download_folder = config.get("download_folder", "downloads")
    if 'max_path' not in st.session_state:
        st.session_state.max_path = config.get("max_path", "")
    
    # Get local device information
    local_ip = get_local_ip()
    hostname = socket.gethostname()
    platform_info = f"{platform.system()} {platform.release()}"
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Display device information in a clean layout
    st.markdown("### Device Information")
    
    # Create two columns for better layout
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("#### Basic Information")
        st.write(f"**Hostname:** {hostname}")
        st.write(f"**IP Address:** {local_ip}")
        st.write(f"**Platform:** {platform_info}")
        st.write(f"**Status:** Online")
        st.write(f"**Last Seen:** {current_time}")
        
        st.markdown("#### Network Details")
        st.write(f"**Port:** {PORT}")
        st.write(f"**Connection Type:** LAN")
        
        st.markdown("#### System Information")
        st.write(f"**Machine:** {platform.machine()}")
        st.write(f"**Processor:** {platform.processor()}")
        st.write(f"**Python Version:** {platform.python_version()}")
        
        # Add download folder configuration
        st.markdown("#### Download Settings")
        current_folder = st.session_state.download_folder
        st.write(f"**Current Download Folder:** {os.path.abspath(current_folder)}")
        
        # Add manual path input option
        new_folder_path = st.text_input("Enter download folder path manually:", value=current_folder)
        
        col3, col4, col5 = st.columns([1, 1, 1])
        with col3:
            if st.button("Choose Folder (File Picker)"):
                new_folder = open_folder_picker()
                if new_folder and new_folder != current_folder:
                    if change_download_folder(new_folder):
                        st.success(f"Download folder changed to: {os.path.abspath(new_folder)}")
                        st.rerun()
        
        with col4:
            if st.button("Save Manual Path"):
                if new_folder_path and new_folder_path != current_folder:
                    if change_download_folder(new_folder_path):
                        st.success(f"Download folder changed to: {os.path.abspath(new_folder_path)}")
                        st.rerun()
        
        with col5:
            if st.button("Reset to Default"):
                default_folder = "downloads"
                if current_folder != default_folder:
                    if change_download_folder(default_folder):
                        st.success(f"Download folder reset to default: {os.path.abspath(default_folder)}")
                        st.rerun()
        
        # Add 3ds Max configuration
        if platform.system() == 'Windows':
            st.markdown("#### 3ds Max Settings")
            current_max_path = st.session_state.max_path
            if current_max_path:
                st.write(f"**Current 3ds Max Path:** {current_max_path}")
            else:
                st.write("**Current 3ds Max Path:** Not configured")
            
            # Add manual path input option
            new_max_path = st.text_input("Enter 3ds Max path manually:", value=current_max_path)
            
            col6, col7, col8 = st.columns([1, 1, 1])
            with col6:
                if st.button("Choose 3ds Max (File Picker)"):
                    new_path = open_file_picker()
                    if new_path and new_path != current_max_path:
                        if change_max_path(new_path):
                            st.success(f"3ds Max path changed to: {new_path}")
                            st.rerun()
            
            with col7:
                if st.button("Save Manual Path", key="save_max_path"):
                    if new_max_path and new_max_path != current_max_path:
                        if change_max_path(new_max_path):
                            st.success(f"3ds Max path changed to: {new_max_path}")
                            st.rerun()
            
            with col8:
                if st.button("Clear Path", key="clear_max_path"):
                    if current_max_path:
                        if change_max_path(""):
                            st.success("3ds Max path cleared")
                            st.rerun()
    
    with col2:
        st.markdown("#### Quick Actions")
        if st.button("Open Local App"):
            st.markdown(f"[Open Connection](http://localhost:{PORT})")
        
        st.markdown("#### Connection Status")
        st.success("✅ Connected to Network")
        st.info("Your device is visible to other users on the same network")
        
        st.markdown("#### Tips")
        st.info("""
        - Keep the app running to stay visible to other devices
        - Make sure your firewall allows connections on port 8501
        - Other devices can find you as long as you're on the same network
        - Choose a download folder with sufficient storage space
        - Configure 3ds Max path to enable script execution
        """)
    
    # Add a section for troubleshooting
    with st.expander("🔧 Troubleshooting"):
        st.markdown("""
        If other devices cannot see your device:
        1. Check if you're on the same network as other devices
        2. Ensure your firewall is not blocking port 8501
        3. Try running the app with administrator privileges
        4. Check if your antivirus is not blocking the connection
        5. Restart the app if the issue persists
        
        If you have issues with the download folder:
        1. Make sure the folder path is valid and accessible
        2. Ensure you have write permissions for the folder
        3. Check if there's enough disk space
        4. Try using an absolute path if relative path doesn't work
        
        If you have issues with 3ds Max:
        1. Make sure the path points to the correct 3dsmax.exe file
        2. Ensure you have the correct version of 3ds Max installed
        3. Check if you have necessary permissions to run 3ds Max
        4. Try running the app with administrator privileges
        """)

if __name__ == "__main__":
    main() 