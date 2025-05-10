import streamlit as st
import socket
import ipaddress
import concurrent.futures
from datetime import datetime
import requests
import json
import platform
import subprocess

# Constants
PORT = 8501  # Streamlit default port
APP_IDENTIFIER = "LAN-FILE-SHARING-APP"  # Unique identifier for our app

def get_local_ip():
    """Get the local IP address of the machine."""
    try:
        # Platform-specific IP detection
        if platform.system() == 'Windows':
            # Windows-specific method
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
        else:
            # Unix-based systems (macOS and Linux)
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
        return local_ip
    except Exception as e:
        st.warning(f"Could not determine local IP: {str(e)}")
        return "127.0.0.1"

def get_network_range():
    """Get the network range based on local IP and platform."""
    local_ip = get_local_ip()
    ip_parts = local_ip.split('.')
    
    # Default to /24 subnet
    subnet = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.0/24"
    
    # Platform-specific network range detection
    if platform.system() == 'Windows':
        try:
            # Try to get subnet mask from Windows
            output = subprocess.check_output('ipconfig', shell=True).decode()
            for line in output.split('\n'):
                if 'Subnet Mask' in line:
                    mask = line.split(':')[-1].strip()
                    # Convert subnet mask to CIDR notation
                    cidr = sum([bin(int(x)).count('1') for x in mask.split('.')])
                    subnet = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.0/{cidr}"
                    break
        except:
            pass
    elif platform.system() == 'Darwin':  # macOS
        try:
            # Try to get subnet mask from macOS
            output = subprocess.check_output('ifconfig', shell=True).decode()
            for line in output.split('\n'):
                if 'netmask' in line:
                    mask = line.split('netmask')[-1].strip().split()[0]
                    # Convert subnet mask to CIDR notation
                    cidr = sum([bin(int(x)).count('1') for x in mask.split('.')])
                    subnet = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.0/{cidr}"
                    break
        except:
            pass
    else:  # Linux
        try:
            # Try to get subnet mask from Linux
            output = subprocess.check_output('ip addr', shell=True).decode()
            for line in output.split('\n'):
                if 'inet ' in line and 'brd' in line:
                    cidr = line.split('/')[-1].split()[0]
                    subnet = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.0/{cidr}"
                    break
        except:
            pass
    
    return subnet

def check_app_instance(ip):
    """Check if a host is running our Streamlit app."""
    try:
        # Try to connect to the Streamlit port and check for our app
        url = f"http://{ip}:{PORT}/_stcore/stream"
        response = requests.get(url, timeout=1)
        
        if response.status_code == 200:
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
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        future_to_ip = {executor.submit(check_app_instance, str(ip)): str(ip) for ip in network.hosts()}
        for future in concurrent.futures.as_completed(future_to_ip):
            result = future.result()
            if result:
                active_hosts.append(result)
    
    return active_hosts

def main():
    st.title("Connected Devices")
    
    # Display local IP address and platform
    local_ip = get_local_ip()
    st.info(f"Your local IP address: {local_ip}")
    st.info(f"Platform: {platform.system()} {platform.release()}")
    
    # Add a refresh button
    if st.button("🔄 Refresh Device List"):
        st.experimental_rerun()
    
    # Scan for devices
    with st.spinner("Scanning for other instances of the app..."):
        active_hosts = scan_network()
    
    if active_hosts:
        # Create a table for connected devices
        st.markdown("### Active App Instances")
        
        # Create a container for the device list
        device_container = st.container()
        
        with device_container:
            for host in active_hosts:
                with st.expander(f"📱 {host['hostname']} ({host['ip']})"):
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        st.write(f"**Status:** {host['status']}")
                        st.write(f"**Last Seen:** {host['last_seen']}")
                        st.write(f"**Platform:** {host['platform']}")
                    with col2:
                        if st.button("Connect", key=f"connect_{host['ip']}"):
                            st.markdown(f"[Open Connection](http://{host['ip']}:{PORT})")
    else:
        st.info("No other instances of the app found in the network.")

if __name__ == "__main__":
    main() 