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
SCAN_INTERVAL = 5  # Seconds between scans
BROADCAST_INTERVAL = 10  # Seconds between broadcasts

# Initialize session state
if 'active_connections' not in st.session_state:
    st.session_state.active_connections = {}
if 'last_scan_time' not in st.session_state:
    st.session_state.last_scan_time = datetime.now()
if 'is_scanning' not in st.session_state:
    st.session_state.is_scanning = False

def broadcast_presence():
    """Broadcast this app's presence to the network."""
    while True:
        try:
            # Create a UDP socket for broadcasting
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            
            # Prepare broadcast message
            message = {
                'type': 'presence',
                'ip': get_local_ip(),
                'hostname': socket.gethostname(),
                'platform': platform.system(),
                'timestamp': datetime.now().isoformat()
            }
            
            # Broadcast to the network
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
                # Update active connections
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
            try:
                # Try to get hostname
                hostname = socket.gethostbyaddr(ip)[0]
            except:
                hostname = "Unknown"
            
            return {
                "ip": ip,
                "hostname": hostname,
                "status": "Online",
                "last_seen": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "platform": platform.system()
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

def continuous_scan():
    """Continuously scan the network for other instances."""
    while True:
        try:
            st.session_state.is_scanning = True
            active_hosts = scan_network()
            
            # Update active connections
            for host in active_hosts:
                st.session_state.active_connections[host['ip']] = host
            
            # Remove stale connections (not seen in last 30 seconds)
            current_time = datetime.now()
            stale_ips = []
            for ip, host in st.session_state.active_connections.items():
                last_seen = datetime.strptime(host['last_seen'], "%Y-%m-%d %H:%M:%S")
                if (current_time - last_seen).total_seconds() > 30:
                    stale_ips.append(ip)
            
            for ip in stale_ips:
                del st.session_state.active_connections[ip]
            
            st.session_state.last_scan_time = current_time
            st.session_state.is_scanning = False
            
            time.sleep(SCAN_INTERVAL)
        except Exception as e:
            print(f"Scan error: {e}")
            st.session_state.is_scanning = False
            time.sleep(SCAN_INTERVAL)

def start_continuous_scan():
    """Start the continuous scanning thread."""
    if 'scan_thread' not in st.session_state:
        st.session_state.scan_thread = threading.Thread(target=continuous_scan, daemon=True)
        st.session_state.scan_thread.start()

def main():
    st.title("Connected Devices")
    
    # Display local IP address and platform
    local_ip = get_local_ip()
    st.info(f"Your local IP address: {local_ip}")
    st.info(f"Platform: {platform.system()} {platform.release()}")
    
    # Add a refresh button
    if st.button("🔄 Refresh Now"):
        st.session_state.is_scanning = True
        active_hosts = scan_network()
        
        # Update active connections
        st.session_state.active_connections = {
            host['ip']: host for host in active_hosts
        }
        st.session_state.is_scanning = False
    
    # Display active connections
    if st.session_state.active_connections:
        st.markdown("### Active App Instances")
        
        # Create a container for the device list
        device_container = st.container()
        
        with device_container:
            for ip, host in st.session_state.active_connections.items():
                with st.expander(f"📱 {host['hostname']} ({host['ip']})"):
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        st.write(f"**Status:** {host['status']}")
                        st.write(f"**Last Seen:** {host['last_seen']}")
                        st.write(f"**Platform:** {host['platform']}")
                    with col2:
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