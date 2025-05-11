import requests
import socket
import os
import time
import json
from pathlib import Path

# Constants
UPLOAD_FOLDER = "downloads"
TEST_FILE_NAME = "test_transfer.txt"
TEST_FILE_CONTENT = "This is a test file for transfer verification.\nTimestamp: {timestamp}"
EVENT_FILE = "file_events.json"

def create_test_file():
    """Create a test file with timestamp."""
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    
    test_file_path = os.path.join(UPLOAD_FOLDER, TEST_FILE_NAME)
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    content = TEST_FILE_CONTENT.format(timestamp=timestamp)
    
    with open(test_file_path, "w") as f:
        f.write(content)
    
    print(f"✅ Created test file: {test_file_path}")
    return test_file_path

def get_local_ip():
    """Get the local IP address of the machine."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception as e:
        print(f"Could not determine local IP: {str(e)}")
        return "127.0.0.1"

def send_file_to_flask(file_path, ip, port=8502):
    """Send file to Flask server."""
    try:
        url = f"http://{ip}:{port}/upload"
        with open(file_path, 'rb') as f:
            files = {'file': f}
            print(f"Sending file to Flask server at {url}...")
            response = requests.post(url, files=files, timeout=10)
            
            if response.status_code == 200:
                print("✅ File sent successfully to Flask server")
                return True
            else:
                print(f"❌ Failed to send file. Status code: {response.status_code}")
                print(f"Response: {response.text}")
                return False
    except Exception as e:
        print(f"❌ Error sending file: {str(e)}")
        return False

def verify_file_received():
    """Verify that the file was received and saved correctly."""
    received_file_path = os.path.join(UPLOAD_FOLDER, TEST_FILE_NAME)
    
    # Wait for file to be received (max 5 seconds)
    max_wait = 5
    start_time = time.time()
    while not os.path.exists(received_file_path):
        if time.time() - start_time > max_wait:
            print("❌ File was not received within timeout period")
            return False
        time.sleep(0.5)
    
    # Verify file contents
    try:
        with open(received_file_path, 'r') as f:
            content = f.read()
            if TEST_FILE_CONTENT.split('\n')[0] in content:
                print("✅ File received and verified successfully")
                print(f"File contents: {content}")
                return True
            else:
                print("❌ File contents do not match expected content")
                return False
    except Exception as e:
        print(f"❌ Error verifying file: {str(e)}")
        return False

def verify_notification():
    """Verify that the notification was created in the event file."""
    try:
        # Wait for event file to be created/updated (max 5 seconds)
        max_wait = 5
        start_time = time.time()
        while not os.path.exists(EVENT_FILE):
            if time.time() - start_time > max_wait:
                print("❌ Event file was not created within timeout period")
                return False
            time.sleep(0.5)
        
        # Read and verify event
        with open(EVENT_FILE, 'r') as f:
            events = json.load(f)
            
        # Find our test file event
        for event in events:
            if (event['type'] == 'file_received' and 
                event['filename'] == TEST_FILE_NAME):
                print("✅ File transfer notification verified")
                print(f"Event details: {event}")
                return True
        
        print("❌ No matching notification found in event file")
        return False
    except Exception as e:
        print(f"❌ Error verifying notification: {str(e)}")
        return False

def cleanup():
    """Clean up test files."""
    try:
        # Remove test file from upload folder
        test_file_path = os.path.join(UPLOAD_FOLDER, TEST_FILE_NAME)
        if os.path.exists(test_file_path):
            os.remove(test_file_path)
            print("✅ Cleaned up test file")
        
        # Clear event file
        if os.path.exists(EVENT_FILE):
            with open(EVENT_FILE, 'w') as f:
                json.dump([], f)
            print("✅ Cleaned up event file")
    except Exception as e:
        print(f"❌ Error during cleanup: {str(e)}")

def main():
    print("\n=== Starting File Transfer Test ===")
    print("-" * 50)
    
    # Get local IP
    local_ip = get_local_ip()
    print(f"Testing with IP: {local_ip}")
    
    # Create test file
    test_file_path = create_test_file()
    
    try:
        # Send file to Flask
        if send_file_to_flask(test_file_path, local_ip):
            # Verify file was received
            if verify_file_received():
                # Verify notification was created
                if verify_notification():
                    print("\n✅ File transfer test completed successfully!")
                else:
                    print("\n❌ File transfer test failed: Notification verification failed")
            else:
                print("\n❌ File transfer test failed: File verification failed")
        else:
            print("\n❌ File transfer test failed: Could not send file")
    finally:
        print('f')
        # Clean up
        #cleanup()

if __name__ == "__main__":
    main() 