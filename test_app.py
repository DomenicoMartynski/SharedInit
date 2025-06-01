import unittest
import os
import sys
import json
import tempfile
import shutil
from unittest.mock import patch, MagicMock
from datetime import datetime

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock Streamlit to prevent warnings
sys.modules['streamlit'] = MagicMock()
sys.modules['streamlit.runtime'] = MagicMock()
sys.modules['streamlit.runtime.scriptrunner_utils'] = MagicMock()
sys.modules['streamlit.runtime.state'] = MagicMock()

from app import (
    get_local_ip,
    get_network_range,
    check_app_instance,
    scan_network,
    get_file_mime_type,
    is_file_size_allowed,
    get_file_extension,
    is_matlab_file,
    load_config
)

# ANSI color codes for console output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

class TestResult(unittest.TestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.successes = []
        self.failures = []
        self.errors = []
        self.skipped = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.successes.append(test)
        print(f"{Colors.GREEN}✅ {test._testMethodName} passed successfully!{Colors.ENDC}")

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.failures.append((test, err))
        print(f"{Colors.RED}❌ {test._testMethodName} failed!{Colors.ENDC}")
        print(f"{Colors.RED}Error: {err}{Colors.ENDC}")

    def addError(self, test, err):
        super().addError(test, err)
        self.errors.append((test, err))
        print(f"{Colors.YELLOW}⚠️ {test._testMethodName} had an error!{Colors.ENDC}")
        print(f"{Colors.YELLOW}Error: {err}{Colors.ENDC}")

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.skipped.append((test, reason))
        print(f"{Colors.BLUE}⏭️ {test._testMethodName} was skipped: {reason}{Colors.ENDC}")

class TestAppCore(unittest.TestCase):
    def setUp(self):
        """Set up test environment before each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_config = {
            "download_folder": self.temp_dir,
            "max_path": "/path/to/3dsmax"
        }
        
        # Create a test config file
        with open("app_config.json", "w") as f:
            json.dump(self.test_config, f)

    def tearDown(self):
        """Clean up after each test."""
        shutil.rmtree(self.temp_dir)
        if os.path.exists("app_config.json"):
            os.remove("app_config.json")

    @patch('socket.socket')
    def test_get_local_ip(self, mock_socket):
        """Test getting local IP address."""
        # Mock socket behavior
        mock_socket_instance = MagicMock()
        mock_socket.return_value = mock_socket_instance
        mock_socket_instance.getsockname.return_value = ('192.168.1.100', 12345)
        
        ip = get_local_ip()
        self.assertIsNotNone(ip)
        self.assertTrue(isinstance(ip, str))
        self.assertTrue(len(ip.split('.')) == 4)

    def test_get_network_range(self):
        """Test getting network range from local IP."""
        with patch('app.get_local_ip', return_value='192.168.1.100'):
            network_range = get_network_range()
            self.assertIsNotNone(network_range)
            self.assertTrue(isinstance(network_range, str))
            self.assertTrue(network_range.endswith('/24'))

    @patch('socket.socket')
    @patch('socket.gethostbyaddr')
    @patch('requests.get')
    def test_check_app_instance(self, mock_requests_get, mock_gethostbyaddr, mock_socket):
        """Test checking if an app instance is running on a host."""
        # Mock socket behavior for initial connection
        mock_socket_instance = MagicMock()
        mock_socket.return_value = mock_socket_instance
        mock_socket_instance.connect_ex.return_value = 0  # Connection successful
        
        # Mock hostname lookup
        mock_gethostbyaddr.return_value = ('test-host', [], ['192.168.1.100'])
        
        # Mock HTTP response for platform detection
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {
            'X-Platform': 'Darwin',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'
        }
        mock_requests_get.return_value = mock_response
        
        result = check_app_instance('192.168.1.100')
        self.assertIsNotNone(result)
        self.assertTrue(isinstance(result, dict))
        self.assertIn('ip', result)
        self.assertIn('hostname', result)
        self.assertIn('platform', result)
        self.assertEqual(result['ip'], '192.168.1.100')
        self.assertEqual(result['hostname'], 'test-host')
        self.assertEqual(result['platform'], 'Darwin')
        self.assertEqual(result['status'], 'Online')
        self.assertIn('last_seen', result)

    @patch('app.check_app_instance')
    def test_scan_network(self, mock_check_instance):
        """Test scanning network for app instances."""
        # Mock check_app_instance to return a test device
        mock_check_instance.return_value = {
            'ip': '192.168.1.100',
            'hostname': 'test-device',
            'platform': 'Windows'
        }
        
        with patch('app.get_network_range', return_value='192.168.1.0/24'):
            active_hosts = scan_network()
            self.assertIsNotNone(active_hosts)
            self.assertTrue(isinstance(active_hosts, list))
            if active_hosts:
                self.assertTrue(isinstance(active_hosts[0], dict))

    def test_get_file_mime_type(self):
        """Test getting MIME type of a file."""
        # Create a test file
        test_file = os.path.join(self.temp_dir, 'test.txt')
        with open(test_file, 'w') as f:
            f.write('test content')
        
        mime_type = get_file_mime_type(test_file)
        self.assertIsNotNone(mime_type)
        self.assertTrue(isinstance(mime_type, str))
        self.assertTrue(mime_type.startswith('text/'))

    def test_is_file_size_allowed(self):
        """Test file size allowance check."""
        # Test within limit
        self.assertTrue(is_file_size_allowed(100 * 1024 * 1024))  # 100MB
        
        # Test exceeding limit
        self.assertFalse(is_file_size_allowed(300 * 1024 * 1024))  # 300MB

    def test_get_file_extension(self):
        """Test getting file extension."""
        test_cases = [
            ('test.txt', '.txt'),
            ('document.pdf', '.pdf'),
            ('script.py', '.py'),
            ('no_extension', ''),
            ('multiple.dots.txt', '.txt')
        ]
        
        for filename, expected in test_cases:
            self.assertEqual(get_file_extension(filename), expected)

    def test_is_matlab_file(self):
        """Test MATLAB file detection."""
        # Test MATLAB files
        self.assertTrue(is_matlab_file('script.m'))
        self.assertTrue(is_matlab_file('function.m'))
        
        # Test non-MATLAB files
        self.assertFalse(is_matlab_file('script.py'))
        self.assertFalse(is_matlab_file('document.txt'))

    def test_load_config(self):
        """Test loading configuration."""
        config = load_config()
        self.assertIsNotNone(config)
        self.assertTrue(isinstance(config, dict))
        self.assertIn('download_folder', config)
        self.assertIn('max_path', config)
        self.assertEqual(config['download_folder'], self.temp_dir)
        self.assertEqual(config['max_path'], '/path/to/3dsmax')

def run_tests():
    """Run tests with console output."""
    print(f"\n{Colors.BOLD}Running tests...{Colors.ENDC}\n")
    
    # Create test suite
    suite = unittest.TestLoader().loadTestsFromTestCase(TestAppCore)
    
    # Create custom test result
    result = TestResult()
    
    # Run tests
    suite.run(result)
    
    # Print summary
    print(f"\n{Colors.BOLD}Test Summary:{Colors.ENDC}")
    print(f"{Colors.GREEN}✅ Passed: {len(result.successes)}{Colors.ENDC}")
    print(f"{Colors.RED}❌ Failed: {len(result.failures)}{Colors.ENDC}")
    print(f"{Colors.YELLOW}⚠️ Errors: {len(result.errors)}{Colors.ENDC}")
    print(f"{Colors.BLUE}⏭️ Skipped: {len(result.skipped)}{Colors.ENDC}")
    
    # Print detailed results for failures and errors
    if result.failures or result.errors:
        print(f"\n{Colors.BOLD}Detailed Results:{Colors.ENDC}")
        
        if result.failures:
            print(f"\n{Colors.RED}Failed Tests:{Colors.ENDC}")
            for test, err in result.failures:
                print(f"{Colors.RED}- {test._testMethodName}{Colors.ENDC}")
                print(f"{Colors.RED}  Error: {err}{Colors.ENDC}")
        
        if result.errors:
            print(f"\n{Colors.YELLOW}Tests with Errors:{Colors.ENDC}")
            for test, err in result.errors:
                print(f"{Colors.YELLOW}- {test._testMethodName}{Colors.ENDC}")
                print(f"{Colors.YELLOW}  Error: {err}{Colors.ENDC}")

if __name__ == '__main__':
    run_tests() 