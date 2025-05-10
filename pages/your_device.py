import streamlit as st
import socket
import platform
from datetime import datetime

# Constants
PORT = 8501  # Streamlit default port

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

def main():
    st.title("Your Device")
    
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
        """)

if __name__ == "__main__":
    main() 