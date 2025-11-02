"""Unit tests for the server."""
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from create_tables import create_tables
from server.server import (
    app,
    get_db_conn,
    prune_inactive_devices,
    prune_old_stats
)

# Import the create_tables function
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Get the server version from the config
CONFIG_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'server_config.json'
    )
with open(CONFIG_PATH, 'r', encoding="UTF-8") as f:
    config = json.load(f)
    SERVER_VERSION = config.get('version', '0.0.0')


class TestServer(unittest.TestCase):
    """Test cases for the server."""

    def setUp(self):
        """Set up test environment."""
        self.db_fd, self.db_path = tempfile.mkstemp()
        app.config['TESTING'] = True
        app.config['DATABASE'] = self.db_path
        self.app = app.test_client()

        # Initialize the database with the schema from create_tables.py
        with app.app_context():
            conn = get_db_conn()
            create_tables(conn)
            conn.close()

    def tearDown(self):
        """Tear down test environment."""
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_register_device(self):
        """Test device registration."""
        # First registration
        response = self.app.post('/api/register',
                                 data=json.dumps({
                                     'device_uid': 'test-uid',
                                     'device_name': 'test-device'
                                 }),
                                 content_type='application/json',
                                 headers={'X-Client-Version': SERVER_VERSION})
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['device_id'], 1)

        # Second registration of the same device
        response = self.app.post('/api/register',
                                 data=json.dumps({
                                     'device_uid': 'test-uid',
                                     'device_name': 'test-device-renamed'
                                 }),
                                 content_type='application/json',
                                 headers={'X-Client-Version': SERVER_VERSION})
        self.assertEqual(response.status_code, 200)

    def test_receive_data(self):
        """Test receiving data from a client."""
        # First, register a device
        response = self.app.post(
            '/api/register',
            data=json.dumps({'device_uid': 'test-uid'}),
            content_type='application/json',
            headers={'X-Client-Version': SERVER_VERSION}
        )
        device_data = json.loads(response.data)
        device_id = device_data['device_id']

        # Then, send some data
        metrics = {
            'cpu': {'usage': 50.0, 'frequency': '1000 MHz'},
            'memory': {
                'total': 4, 'used': 1, 'available': 3, 'percentage': 25.0
            },
            'disk': {'total': 100, 'used': 20, 'free': 80, 'percentage': 20.0},
            'network': {'interfaces': {}},
            'temperature': 45.0,
            'uptime': 3600,
            'throttled': '0x0',
            'voltages': {'core': 1.2}
        }
        response = self.app.post('/api/data',
                                 data=json.dumps({
                                     'device_id': device_id,
                                     'metrics': metrics
                                 }),
                                 content_type='application/json',
                                 headers={'X-Client-Version': SERVER_VERSION})
        self.assertEqual(response.status_code, 201)
        data = json.loads(response.data)
        self.assertEqual(data['status'], 'success')

    def test_get_devices(self):
        """Test getting the list of devices."""
        # Register two devices
        self.app.post('/api/register',
                      data=json.dumps({'device_uid': 'test-uid-1'}),
                      content_type='application/json',
                      headers={'X-Client-Version': SERVER_VERSION})
        self.app.post('/api/register',
                      data=json.dumps({'device_uid': 'test-uid-2'}),
                      content_type='application/json',
                      headers={'X-Client-Version': SERVER_VERSION})

        response = self.app.get('/api/devices')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data), 2)

    def test_prune_old_stats(self):
        """Test pruning old statistics."""
        with app.app_context():
            conn = get_db_conn()
            c = conn.cursor()
            # Add a device
            c.execute(
                "INSERT INTO devices (device_uid, device_name) VALUES (?, ?)",
                ('test-uid-prune', 'test-device')
            )
            device_id = c.lastrowid
            # Add an old stat
            old_date = datetime.now(timezone.utc) - timedelta(days=31)
            c.execute("""
                INSERT INTO stats (device_id, timestamp, cpu_usage,
                memory_percentage, disk_percentage)
                VALUES (?, ?, 10, 20, 30)
            """, (device_id, old_date))
            # Add a new stat
            c.execute("""
                INSERT INTO stats (device_id, cpu_usage, memory_percentage,
                disk_percentage)
                VALUES (?, 11, 21, 31)
            """, (device_id,))
            conn.commit()

            prune_old_stats(conn)

            c.execute("SELECT COUNT(*) FROM stats")
            count = c.fetchone()[0]
            self.assertEqual(count, 1)
            conn.close()

    def test_prune_inactive_devices(self):
        """Test pruning inactive devices."""
        with app.app_context():
            conn = get_db_conn()
            c = conn.cursor()
            # Add an inactive device
            old_date = datetime.now(timezone.utc) - timedelta(days=8)
            c.execute("""
                INSERT INTO devices (device_uid, device_name, last_seen)
                VALUES (?, ?, ?)
            """, ('inactive-uid-prune', 'inactive-device', old_date))
            # Add an active device
            c.execute("""
                INSERT INTO devices (device_uid, device_name)
                VALUES (?, ?)
            """, ('active-uid-prune', 'active-device'))
            conn.commit()

            prune_inactive_devices(conn)

            c.execute("SELECT COUNT(*) FROM devices")
            count = c.fetchone()[0]
            self.assertEqual(count, 1)
            conn.close()


if __name__ == '__main__':
    unittest.main()
