import streamlit as st
import socket
import ipaddress
import concurrent.futures
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
    except Exception:
        return "127.0.0.1"

def get_network_range():
    """Get the network range based on local IP."""
    local_ip = get_local_ip()
    ip_parts = local_ip.split('.')
    return f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.0/24"

def check_host(ip):
    """Check if a host is reachable and running Streamlit."""
    try:
        # Try to connect to the Streamlit port
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
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
                "last_seen": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
    except:
        pass
    return None

def scan_network():
    """Scan the network for other devices running the app."""
    network = ipaddress.ip_network(get_network_range())
    active_hosts = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        future_to_ip = {executor.submit(check_host, str(ip)): str(ip) for ip in network.hosts()}
        for future in concurrent.futures.as_completed(future_to_ip):
            result = future.result()
            if result:
                active_hosts.append(result)
    
    return active_hosts

def main():
    st.title("Connected Devices")
    
    # Display local IP address
    local_ip = get_local_ip()
    st.info(f"Your local IP address: {local_ip}")
    
    # Add a refresh button
    if st.button("🔄 Refresh Device List"):
        st.experimental_rerun()
    
    # Scan for devices
    with st.spinner("Scanning network for devices..."):
        active_hosts = scan_network()
    
    if active_hosts:
        # Create a table for connected devices
        st.markdown("### Active Devices")
        
        # Create a container for the device list
        device_container = st.container()
        
        with device_container:
            for host in active_hosts:
                with st.expander(f"📱 {host['hostname']} ({host['ip']})"):
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        st.write(f"**Status:** {host['status']}")
                        st.write(f"**Last Seen:** {host['last_seen']}")
                    with col2:
                        if st.button("Connect", key=f"connect_{host['ip']}"):
                            st.markdown(f"[Open Connection](http://{host['ip']}:{PORT})")
    else:
        st.info("No other devices found running the app.")

if __name__ == "__main__":
    main() 