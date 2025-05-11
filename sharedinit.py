import subprocess
import sys
import os
import time
import signal
import logging
import atexit
import psutil
import threading

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Store process references
processes = []

def cleanup():
    """Clean up processes on exit."""
    logger.info("Cleaning up processes...")
    for process in processes:
        try:
            if process.poll() is None:  # If process is still running
                process.terminate()
                process.wait(timeout=5)
        except Exception as e:
            logger.error(f"Error terminating process: {str(e)}")
            try:
                process.kill()  # Force kill if terminate doesn't work
            except:
                pass

def run_flask_server():
    """Run the Flask server."""
    logger.info("Starting Flask server...")
    process = subprocess.Popen(
        [sys.executable, "file_server.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    processes.append(process)
    return process

def run_streamlit_server():
    """Run the Streamlit server."""
    logger.info("Starting Streamlit server...")
    process = subprocess.Popen(
        ["streamlit", "run", "app.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    processes.append(process)
    return process

def monitor_processes():
    """Monitor processes and restart if they die."""
    while True:
        for process in processes:
            if process.poll() is not None:  # Process has ended
                logger.error(f"Process {process.pid} died unexpectedly")
                # Restart the appropriate process
                if "file_server.py" in process.args:
                    logger.info("Restarting Flask server...")
                    processes.remove(process)
                    run_flask_server()
                elif "app.py" in process.args:
                    logger.info("Restarting Streamlit server...")
                    processes.remove(process)
                    run_streamlit_server()
        time.sleep(1)

def main():
    # Register cleanup handler
    atexit.register(cleanup)
    
    # Start Flask server
    flask_process = run_flask_server()
    
    # Wait a moment for Flask to start
    time.sleep(2)
    
    # Start Streamlit server
    streamlit_process = run_streamlit_server()
    
    try:
        # Start monitoring in a separate thread
        monitor_thread = threading.Thread(target=monitor_processes, daemon=True)
        monitor_thread.start()
        
        # Keep the script running
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down servers...")
        cleanup()
        logger.info("Servers shut down successfully")

if __name__ == "__main__":
    main() 