import unittest
import os
import sys
import json
import tempfile
import shutil
import time
from unittest.mock import patch, MagicMock
from datetime import datetime
import random
import string
import statistics
import logging
import socket
import requests
from concurrent.futures import ThreadPoolExecutor
import ipaddress
from collections import defaultdict

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock Streamlit to prevent warnings
sys.modules['streamlit'] = MagicMock()
sys.modules['streamlit.runtime'] = MagicMock()
sys.modules['streamlit.runtime.scriptrunner_utils'] = MagicMock()
sys.modules['streamlit.runtime.state'] = MagicMock()

# Disable logging during tests
logging.disable(logging.CRITICAL)

from app import (
    send_file_to_device,
    send_file_to_selected_devices,
    MAX_FILE_SIZE,
    get_local_ip,
    get_network_range,
    check_app_instance
)

class TestPerformance(unittest.TestCase):
    def setUp(self):
        """Set up test environment before each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_files = {}
        self.iterations = 50  # Number of iterations for each test
        
        # Create all test files once at the start
        self.create_all_test_files()
        
        # Try to find real devices first
        self.real_devices = self.find_real_devices()
        if self.real_devices:
            print(f"\nFound {len(self.real_devices)} real devices:")
            for device in self.real_devices:
                print(f"- {device['hostname']} ({device['ip']})")
        else:
            print("\nNo real devices found, using simulated devices")
            self.real_devices = [
                {'ip': f'192.168.1.{i}', 'hostname': f'device-{i}', 'platform': 'Windows'}
                for i in range(1, 6)  # 5 test devices
            ]

    def tearDown(self):
        """Clean up after each test."""
        shutil.rmtree(self.temp_dir)
        for file_path in self.test_files.values():
            if os.path.exists(file_path):
                os.remove(file_path)

    def create_all_test_files(self):
        """Create all test files once at the start."""
        # Create single files of different sizes
        test_sizes = [1, 5, 50, 100, 200]
        for size in test_sizes:
            self.create_test_file(size)
        
        # Create 5 files of 1MB each for multiple file tests
        for i in range(5):
            self.create_test_file(1, f'test_multiple_{i+1}.bin')

    def create_test_file(self, size_mb, filename=None):
        """Create a test file of specified size."""
        if filename is None:
            filename = f'test_{size_mb}MB.bin'
        file_path = os.path.join(self.temp_dir, filename)
        
        # Generate random content
        content = ''.join(random.choices(string.ascii_letters + string.digits, k=1024))
        with open(file_path, 'w') as f:
            for _ in range(size_mb * 1024):  # Write content multiple times to reach desired size
                f.write(content)
        
        self.test_files[filename] = file_path
        return file_path

    def find_real_devices(self):
        """Find real devices running the app on the network."""
        real_devices = []
        local_ip = get_local_ip()
        network_range = get_network_range()
        
        # Create a network object from the range
        network = ipaddress.ip_network(network_range)
        
        # Scan the network for devices
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = []
            for ip in network.hosts():
                if str(ip) != local_ip:  # Skip local IP
                    futures.append(executor.submit(self.check_device, str(ip)))
            
            for future in futures:
                result = future.result()
                if result:
                    real_devices.append(result)
        
        return real_devices

    def check_device(self, ip):
        """Check if a device is running the app."""
        try:
            result = check_app_instance(ip)
            if result and result.get('status') == 'Online':
                return result
        except Exception:
            pass
        return None

    def run_test_iterations(self, test_func, *args, **kwargs):
        """Run a test function multiple times and collect statistics."""
        times = []
        successes = 0
        
        for i in range(self.iterations):
            try:
                start_time = time.time()
                test_func(*args, **kwargs)
                end_time = time.time()
                times.append(end_time - start_time)
                successes += 1
                #if (i + 1) % 10 == 0:  # Progress update every 10 iterations
                    #print(f"Completed {i + 1}/{self.iterations} iterations")
            except Exception as e:
                print(f"Iteration {i + 1} failed: {str(e)}")
                continue
        
        return {
            'success_rate': (successes / self.iterations) * 100,
            'avg_time': statistics.mean(times) if times else 0,
            'std_dev': statistics.stdev(times) if len(times) > 1 else 0,
            'min_time': min(times) if times else 0,
            'max_time': max(times) if times else 0
        }

    def test_file_transfer_single_device(self):
        """Test time taken to transfer multiple files to a single device."""
        print("\n=== Single Device File Transfer Performance ===")
        print("Files\tAvg Time (s)\tStd Dev (s)\tMin Time (s)\tMax Time (s)\tSuccess Rate\tAvg Speed (MB/s)")
        print("-" * 100)

        # Test sending 1 to 5 files
        for num_files in range(1, 6):
            def transfer_files():
                if self.real_devices:
                    device = self.real_devices[0]
                    for i in range(num_files):
                        send_file_to_device(self.test_files[f'test_multiple_{i+1}.bin'], device['ip'])
                else:
                    with patch('requests.post', side_effect=lambda *args, **kwargs: time.sleep(0.1)) as mock_post:
                        for i in range(num_files):
                            send_file_to_device(self.test_files[f'test_multiple_{i+1}.bin'], self.real_devices[0]['ip'])
            
            results = self.run_test_iterations(transfer_files)
            avg_speed = (num_files * 1) / results['avg_time'] if results['avg_time'] > 0 else 0
            
            print(f"{num_files}\t{results['avg_time']:.3f}\t{results['std_dev']:.3f}\t"
                  f"{results['min_time']:.3f}\t{results['max_time']:.3f}\t"
                  f"{results['success_rate']:.1f}%\t{avg_speed:.2f}")

    def test_file_transfer_multiple_devices(self):
        """Test time taken to transfer files to multiple devices."""
        print("\n=== Multiple Devices File Transfer Performance ===")
        print("Files\tDevices\tAvg Time (s)\tStd Dev (s)\tMin Time (s)\tMax Time (s)\tSuccess Rate\tAvg Speed (MB/s)")
        print("-" * 110)

        # Limit to available real devices or max 5 simulated devices
        max_devices = min(len(self.real_devices), 5) if self.real_devices else 5
        
        # Test different combinations of files and devices
        for num_files in range(1, 6):
            for num_devices in range(1, max_devices + 1):
                def transfer_files():
                    if self.real_devices:
                        selected_devices = self.real_devices[:num_devices]
                        selected_ips = [device['ip'] for device in selected_devices]
                        for i in range(num_files):
                            send_file_to_selected_devices(self.test_files[f'test_multiple_{i+1}.bin'], selected_ips)
                    else:
                        with patch('requests.post', side_effect=lambda *args, **kwargs: time.sleep(0.1)) as mock_post:
                            selected_devices = self.real_devices[:num_devices]
                            selected_ips = [device['ip'] for device in selected_devices]
                            for i in range(num_files):
                                send_file_to_selected_devices(self.test_files[f'test_multiple_{i+1}.bin'], selected_ips)
                
                results = self.run_test_iterations(transfer_files)
                total_data = num_files * num_devices  # Total MB transferred
                avg_speed = total_data / results['avg_time'] if results['avg_time'] > 0 else 0
                
                print(f"{num_files}\t{num_devices}\t{results['avg_time']:.3f}\t{results['std_dev']:.3f}\t"
                      f"{results['min_time']:.3f}\t{results['max_time']:.3f}\t"
                      f"{results['success_rate']:.1f}%\t{avg_speed:.2f}")

    def test_file_size_transfer(self):
        """Test time taken to transfer files of different sizes."""
        print("\n=== File Size Transfer Performance ===")
        print("Size (MB)\tAvg Time (s)\tStd Dev (s)\tMin Time (s)\tMax Time (s)\tSuccess Rate\tAvg Speed (MB/s)")
        print("-" * 100)

        # Test different file sizes
        test_sizes = [1, 5, 50, 100, 200]
        
        for size in test_sizes:
            def transfer_file():
                if self.real_devices:
                    device = self.real_devices[0]
                    send_file_to_device(self.test_files[f'test_{size}MB.bin'], device['ip'])
                else:
                    with patch('requests.post', side_effect=lambda *args, **kwargs: time.sleep(0.1)) as mock_post:
                        send_file_to_device(self.test_files[f'test_{size}MB.bin'], self.real_devices[0]['ip'])
            
            results = self.run_test_iterations(transfer_file)
            avg_speed = size / results['avg_time'] if results['avg_time'] > 0 else 0
            
            print(f"{size}\t{results['avg_time']:.3f}\t{results['std_dev']:.3f}\t"
                  f"{results['min_time']:.3f}\t{results['max_time']:.3f}\t"
                  f"{results['success_rate']:.1f}%\t{avg_speed:.2f}")

    def test_transfer_reliability(self):
        """Test transfer reliability with multiple attempts."""
        print("\n=== Transfer Reliability Test ===")
        print("Size (MB)\tSuccess Rate\tAvg Time (s)\tStd Dev (s)\tMin Time (s)\tMax Time (s)\tAvg Speed (MB/s)")
        print("-" * 100)

        test_sizes = [1, 5, 50, 100]
        
        for size in test_sizes:
            def transfer_file():
                if self.real_devices:
                    device = self.real_devices[0]
                    send_file_to_device(self.test_files[f'test_{size}MB.bin'], device['ip'])
                else:
                    with patch('requests.post', side_effect=lambda *args, **kwargs: time.sleep(0.1)) as mock_post:
                        send_file_to_device(self.test_files[f'test_{size}MB.bin'], self.real_devices[0]['ip'])
            
            results = self.run_test_iterations(transfer_file)
            avg_speed = size / results['avg_time'] if results['avg_time'] > 0 else 0
            
            print(f"{size}\t{results['success_rate']:.1f}%\t{results['avg_time']:.3f}\t{results['std_dev']:.3f}\t"
                  f"{results['min_time']:.3f}\t{results['max_time']:.3f}\t{avg_speed:.2f}")

def run_performance_tests():
    """Run performance tests and display results."""
    print("\n=== Starting Performance Tests ===\n")
    
    # Create test suite
    suite = unittest.TestLoader().loadTestsFromTestCase(TestPerformance)
    
    # Run tests
    result = unittest.TestResult()
    suite.run(result)
    
    print("\n=== Performance Tests Completed ===")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")

if __name__ == '__main__':
    run_performance_tests() 