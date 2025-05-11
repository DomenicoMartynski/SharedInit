import requests
import socket
import time
import sys

def check_streamlit_connection(ip, port=8501):
    """Check if Streamlit server is running and accessible."""
    try:
        response = requests.get(f"http://{ip}:{port}", timeout=5)
        if response.status_code == 200:
            print(f"✅ Streamlit server is running on {ip}:{port}")
            return True
        else:
            print(f"❌ Streamlit server returned status code {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Could not connect to Streamlit server on {ip}:{port}")
        print(f"Error: {str(e)}")
        return False

def check_flask_connection(ip, port=8502):
    """Check if Flask server is running and accessible."""
    try:
        # Try to send a small test file
        test_data = {'file': ('test.txt', b'This is a test file')}
        response = requests.post(f"http://{ip}:{port}/upload", files=test_data, timeout=5)
        if response.status_code == 200:
            print(f"✅ Flask server is running on {ip}:{port}")
            return True
        else:
            print(f"❌ Flask server returned status code {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Could not connect to Flask server on {ip}:{port}")
        print(f"Error: {str(e)}")
        return False

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

def main():
    # Get local IP
    local_ip = get_local_ip()
    print(f"\nTesting connections for IP: {local_ip}")
    print("-" * 50)

    # Test Streamlit connection
    print("\nTesting Streamlit connection...")
    streamlit_ok = check_streamlit_connection(local_ip)
    
    # Test Flask connection
    print("\nTesting Flask connection...")
    flask_ok = check_flask_connection(local_ip)

    # Summary
    print("\nConnection Test Summary:")
    print("-" * 50)
    print(f"Streamlit (port 8501): {'✅ OK' if streamlit_ok else '❌ Failed'}")
    print(f"Flask (port 8502): {'✅ OK' if flask_ok else '❌ Failed'}")
    
    if streamlit_ok and flask_ok:
        print("\n✅ All connections are working properly!")
    else:
        print("\n❌ Some connections failed. Please check the error messages above.")

if __name__ == "__main__":
    main() 