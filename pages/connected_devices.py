import streamlit as st
import socket
import ipaddress
import concurrent.futures
from datetime import datetime
import requests
import json
import platform
import subprocess
import time
import threading
import queue

# Constants
PORT = 8501  # Streamlit default port
APP_IDENTIFIER = "LAN-FILE-SHARING-APP"  # Unique identifier for our app

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
                
                # If still unknown, try to detect from hostname
                if platform_type == "Unknown":
                    try:
                        # Try to detect platform from hostname patterns
                        hostname_lower = hostname.lower()
                        if 'mac' in hostname_lower or 'darwin' in hostname_lower:
                            platform_type = "Darwin"
                        elif 'win' in hostname_lower:
                            platform_type = "Windows"
                        elif 'linux' in hostname_lower:
                            platform_type = "Linux"
                    except:
                        pass
            except:
                pass

            # Check downloads state
            downloads_enabled = "Unknown"
            try:
                response = requests.post(
                    f"http://{ip}:8502/downloads_enabled",
                    json={'downloads_enabled': True},
                    headers={'Content-Type': 'application/json'},
                    timeout=0.5
                )
                if response.status_code == 200:
                    data = response.json()
                    downloads_enabled = "Enabled" if data.get('downloads_enabled', False) else "Disabled"
            except:
                pass
            
            return {
                "ip": ip,
                "hostname": hostname,
                "status": "Online",
                "last_seen": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "platform": platform_type,
                "downloads_enabled": downloads_enabled
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
    
    # Create progress bar
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        future_to_ip = {
            executor.submit(check_app_instance, ip): ip 
            for ip in ips_to_scan
        }
        
        scanned = 0
        for future in concurrent.futures.as_completed(future_to_ip):
            scanned += 1
            progress = scanned / total_ips
            progress_bar.progress(progress)
            status_text.text(f"Scanning... {scanned}/{total_ips} IPs")
            
            result = future.result()
            if result:
                active_hosts.append(result)
    
    # Clear progress indicators
    progress_bar.empty()
    status_text.empty()
    
    return active_hosts

def main():
    st.title("Connected Devices")
    
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
    
    # Add a refresh button for manual updates
    if st.button("🔄 Refresh Now"):
        with st.spinner("Scanning for devices..."):
            active_hosts = scan_network()
            st.session_state.active_connections = {
                host['ip']: host for host in active_hosts
            }
    
    # Display active connections
    if st.session_state.active_connections:
        st.markdown("### Active App Instances")
        
        # Create a container for the device list
        device_container = st.container()
        
        with device_container:
            for ip, host in st.session_state.active_connections.items():
                with st.expander(f"📱 {host['hostname']} ({host['ip']})"):
                    col1, col2, col3 = st.columns([2, 1, 1])
                    with col1:
                        st.write(f"**Status:** {host['status']}")
                        st.write(f"**Last Seen:** {host['last_seen']}")
                        st.write(f"**Platform:** {host['platform']}")
                    with col2:
                        downloads_state = host.get('downloads_enabled', 'Unknown')
                        st.write(f"**Downloads:** {downloads_state}")
                    with col3:
                        if st.button("Connect", key=f"connect_{ip}"):
                            st.markdown(f"[Open Connection](http://{ip}:{PORT})")
    else:
        st.info("No other instances of the app found in the network.")
        st.warning("""
        If you're running the app on multiple devices but they're not showing up:
        1. Make sure all devices are on the same network
        2. Check if port 8501 is not blocked by your firewall
        3. Try running the app with administrator privileges
        4. Ensure both instances are running the latest version
        """)

if __name__ == "__main__":
    main() 