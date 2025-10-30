import unittest
import json
import os
import sqlite3
from unittest.mock import patch

# Set the path to the server directory to allow for correct imports
import sys
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from server import app
from create_tables import create_tables

class ServerTestCase(unittest.TestCase):
    def setUp(self):
        """Set up a test environment."""
        # Use an in-memory SQLite database for testing
        self.db_fd, app.config['DATABASE'] = ('test.db', 'test.db')
        app.config['TESTING'] = True
        self.app = app.test_client()

        # Mock the get_db_conn to use the in-memory database
        self.conn = sqlite3.connect(':memory:')
        self.conn.row_factory = sqlite3.Row
        create_tables(self.conn) # Create tables in the in-memory db

        # Patch get_db_conn to return our in-memory connection
        self.mock_db_conn = patch('server.get_db_conn', return_value=self.conn)
        self.mock_db_conn.start()

        # Get server version for version-dependent tests
        self.server_version = self.get_server_version()
        self.headers = {'X-Client-Version': self.server_version}

    def tearDown(self):
        """Clean up after tests."""
        self.mock_db_conn.stop()
        self.conn.close()

    def get_server_version(self):
        """Helper to get server version from config."""
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'server_config.json')
        with open(config_path, 'r') as f:
            return json.load(f).get('version', '0.0.0')

    def register_test_device(self, uid='test_uid_123', name='test-device'):
        """Helper function to register a device and return its ID."""
        payload = {'device_uid': uid, 'device_name': name, 'hostname': name}
        response = self.app.post('/api/register', headers=self.headers, json=payload)
        self.assertIn(response.status_code, [200, 201])
        return json.loads(response.data)['device_id']

    # --- Test Cases ---

    def test_01_index_route(self):
        """Test the main index route returns HTML."""
        response = self.app.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<title>Raspberry Pi Status Monitor</title>', response.data)

    def test_02_version_endpoint(self):
        """Test the /api/version endpoint."""
        response = self.app.get('/api/version')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['version'], self.server_version)

    def test_03_register_new_device(self):
        """Test registering a completely new device."""
        payload = {'device_uid': 'new_device_abc', 'device_name': 'New Device', 'hostname': 'new-host'}
        response = self.app.post('/api/register', headers=self.headers, json=payload)
        self.assertEqual(response.status_code, 201) # 201 Created for new resource
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'success')
        self.assertIsInstance(data['device_id'], int)

    def test_04_register_existing_device(self):
        """Test that re-registering an existing device updates it."""
        self.register_test_device(uid='existing_device_123')
        # Register the same device again
        payload = {'device_uid': 'existing_device_123', 'device_name': 'Updated Name'}
        response = self.app.post('/api/register', headers=self.headers, json=payload)
        self.assertEqual(response.status_code, 200) # 200 OK for update

    def test_05_register_bad_request(self):
        """Test registration with missing device_uid."""
        payload = {'device_name': 'Bad Request Device'}
        response = self.app.post('/api/register', headers=self.headers, json=payload)
        self.assertEqual(response.status_code, 400)

    def test_06_get_devices(self):
        """Test the /api/devices endpoint."""
        self.register_test_device(uid='device1', name='Device One')
        self.register_test_device(uid='device2', name='Device Two')
        response = self.app.get('/api/devices')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]['device_name'], 'Device Two') # Ordered by last_seen DESC

    def test_07_receive_data_success(self):
        """Test successfully posting metrics data."""
        device_id = self.register_test_device()
        payload = {
            'device_id': device_id,
            'metrics': {
                'cpu': {'usage': 50.5, 'frequency': '1500 MHz'},
                'memory': {'used': 1.5, 'total': 4.0, 'percentage': 37.5},
                'disk': {'used': 10.0, 'total': 32.0, 'percentage': 31.25},
                'network': {'interfaces': {
                    'eth0': {
                        'bytes_sent': 1024, 'bytes_recv': 2048, 'packets_sent': 10,
                        'packets_recv': 20, 'speed': 1000, 'mtu': 1500, 'is_up': True
                    }
                }}
            }
        }
        response = self.app.post('/api/data', headers=self.headers, json=payload)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(json.loads(response.data)['status'], 'success')

    def test_08_receive_data_bad_request(self):
        """Test posting data with a missing 'metrics' field."""
        device_id = self.register_test_device()
        payload = {'device_id': device_id} # Missing 'metrics'
        response = self.app.post('/api/data', headers=self.headers, json=payload)
        self.assertEqual(response.status_code, 400)

    def test_09_receive_data_unregistered_device(self):
        """Test posting data for a device ID that doesn't exist."""
        payload = {'device_id': 999, 'metrics': {}}
        response = self.app.post('/api/data', headers=self.headers, json=payload)
        self.assertEqual(response.status_code, 404)

    def test_10_get_latest_data(self):
        """Test the /api/latest/<id> endpoint."""
        device_id = self.register_test_device()
        # First post some data
        self.test_07_receive_data_success()
        response = self.app.get(f'/api/latest/{device_id}')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['device_id'], device_id)
        self.assertEqual(data['cpu_usage'], 50.5)
        self.assertIn('eth0', data['network_stats'])

    def test_11_get_history_data(self):
        """Test the /api/history/<id> endpoint."""
        device_id = self.register_test_device()
        self.test_07_receive_data_success() # Post once
        self.test_07_receive_data_success() # Post twice
        response = self.app.get(f'/api/history/{device_id}')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data), 2)
        self.assertIn('timestamp', data[0])
        self.assertIn('cpu_usage', data[0])

if __name__ == '__main__':
    unittest.main()
