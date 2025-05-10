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

# Constants
UPLOAD_FOLDER = "shared_files"
RECEIVED_FOLDER = "received_files"
MAX_FILE_SIZE = 200 * 1024 * 1024  # 200MB max file size

# Create necessary directories
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RECEIVED_FOLDER, exist_ok=True)

# Configure Streamlit page
st.set_page_config(
    page_title="LAN File Sharing App",
    page_icon="📁",
    layout="wide"
)

def get_local_ip():
    """Get the local IP address of the machine."""
    try:
        # Create a socket to get the local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return "127.0.0.1"

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

class FileHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory:
            file_path = event.src_path
            if file_path.startswith(os.path.abspath(RECEIVED_FOLDER)):
                st.toast(f"New file received: {os.path.basename(file_path)}")
                open_file_with_default_app(file_path)

def start_file_watcher():
    """Start watching the received files directory for new files."""
    event_handler = FileHandler()
    observer = Observer()
    observer.schedule(event_handler, RECEIVED_FOLDER, recursive=False)
    observer.start()
    return observer

def is_file_size_allowed(file_size):
    """Check if the file size is within allowed limits."""
    return file_size <= MAX_FILE_SIZE

def get_file_extension(filename):
    """Get the file extension from filename."""
    return os.path.splitext(filename)[1].lower()

def main():
    st.title("LAN File Sharing App")
    
    # Display local IP address
    local_ip = get_local_ip()
    st.info(f"Your local IP address: {local_ip}")
    
    # File upload section
    st.header("Upload File")
    
    # Define allowed file types
    allowed_types = [
        "pdf", "doc", "docx", "txt", "jpg", "jpeg", "png", "gif",
        "mp3", "mp4", "avi", "mov", "zip", "rar", "xlsx", "xls",
        "ppt", "pptx", "csv"
    ]
    
    uploaded_file = st.file_uploader(
        "Choose a file to share",
        type=allowed_types,
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
            if file_extension[1:] not in allowed_types:
                st.error(f"File type {file_extension} is not allowed")
                return

            # Save the uploaded file
            file_path = os.path.join(UPLOAD_FOLDER, uploaded_file.name)
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            st.success(f"File uploaded successfully: {uploaded_file.name}")
            
            # Clear the file uploader
            st.experimental_rerun()
            
        except Exception as e:
            st.error(f"Error uploading file: {str(e)}")
            st.error("Please try again with a different file or check file permissions.")
    
    # Display shared files
    st.header("Shared Files")
    shared_files = os.listdir(UPLOAD_FOLDER)
    if shared_files:
        for file in shared_files:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(file)
            with col2:
                if st.button("Download", key=f"download_{file}"):
                    file_path = os.path.join(UPLOAD_FOLDER, file)
                    try:
                        with open(file_path, "rb") as f:
                            st.download_button(
                                label="Click to download",
                                data=f,
                                file_name=file,
                                key=f"download_btn_{file}",
                                mime=mimetypes.guess_type(file)[0]
                            )
                    except Exception as e:
                        st.error(f"Error downloading file: {str(e)}")
    else:
        st.write("No files shared yet.")

if __name__ == "__main__":
    # Start file watcher in a separate thread
    observer = start_file_watcher()
    try:
        main()
    finally:
        observer.stop()
        observer.join() 