"""Unit tests for the client."""
import json
import os
import sqlite3
import unittest
from unittest.mock import patch, MagicMock
import importlib.util
import requests

# Load the client module from file
client_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'client.py'))
spec = importlib.util.spec_from_file_location("client", client_path)
client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)


class MockSQLiteConnection:
    """Mock SQLite connection that prevents actual closing in tests."""

    def __init__(self, in_memory_conn):
        self._real_conn = in_memory_conn
        self._closed = False
        self.row_factory = None

    def cursor(self):
        """Return a mock cursor that respects the row factory."""
        if self._closed:
            raise sqlite3.ProgrammingError("Cannot operate on a closed database.")
        return MockSQLiteCursor(self._real_conn.cursor(), self.row_factory)

    def commit(self):
        """Commit changes to the database."""
        if self._closed:
            raise sqlite3.ProgrammingError("Cannot operate on a closed database.")
        return self._real_conn.commit()

    def close(self):
        """Mock close method that does not actually close the connection."""
        # Don't actually close the connection, just mark it as closed
        self._closed = True
        # Print statement to show the mock is working
        print("Mock close called (connection not actually closed)")

    def __getattr__(self, name):
        # Delegate all other attributes to the real connection
        return getattr(self._real_conn, name)


class MockSQLiteCursor:
    """Mock SQLite cursor that handles row factory properly."""

    def __init__(self, real_cursor, row_factory):
        self._real_cursor = real_cursor
        self.row_factory = row_factory

    def execute(self, *args, **kwargs):
        """Execute a SQL command."""
        return self._real_cursor.execute(*args, **kwargs)

    def fetchall(self):
        """Fetch all rows, applying the row factory if set."""
        rows = self._real_cursor.fetchall()
        if self.row_factory == sqlite3.Row:
            # Convert tuples to dict-like objects that support column access by name
            description = self._real_cursor.description
            if description:
                column_names = [desc[0] for desc in description]
                return [DictRow(zip(column_names, row)) for row in rows]
        return rows

    def fetchone(self):
        """Fetch one row, applying the row factory if set."""
        row = self._real_cursor.fetchone()
        if self.row_factory == sqlite3.Row and row is not None:
            description = self._real_cursor.description
            if description:
                column_names = [desc[0] for desc in description]
                return DictRow(zip(column_names, row))
        return row

    def __getattr__(self, name):
        # Delegate all other attributes to the real cursor
        return getattr(self._real_cursor, name)


class DictRow:
    """Simple dict-like object to simulate sqlite3.Row behavior."""

    def __init__(self, items):
        self._data = dict(items)

    def __getitem__(self, key):
        if isinstance(key, str):
            return self._data[key]
        # For integer indices, return the value at that position
        return list(self._data.values())[key]

    def __iter__(self):
        return iter(self._data.values())

    def keys(self):
        """Return the keys of the row."""
        return self._data.keys()

    def __len__(self):
        return len(self._data)


class TestClient(unittest.TestCase):
    """Test cases for the client."""

    def setUp(self):
        """Set up test environment."""
        self.real_conn = sqlite3.connect(':memory:')
        c = self.real_conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS metrics_cache (
                     id INTEGER PRIMARY KEY AUTOINCREMENT,
                     timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                     metrics_json TEXT
                     )''')
        self.real_conn.commit()

        # Create our mock connection
        self.mock_conn = MockSQLiteConnection(self.real_conn)
    
        # Mock the sqlite3.connect to return our mock connection
        self.mock_connect = patch('sqlite3.connect', return_value=self.mock_conn)
        self.mock_connect.start()

    def tearDown(self):
        """Tear down test environment."""
        self.mock_connect.stop()
        self.real_conn.close()

    def test_get_hostname(self):
        """Test getting the hostname."""
        with patch('subprocess.check_output') as mock_subprocess:
            mock_subprocess.return_value = b'test-hostname\n'
            hostname = client.get_hostname()
            self.assertEqual(hostname, 'test-hostname')

    def test_get_device_uid(self):
        """Test getting the device UID."""
        with patch('uuid.getnode') as mock_getnode:
            mock_getnode.return_value = 0x1234567890ab
            uid = client.get_device_uid()
            self.assertEqual(uid, '12:34:56:78:90:ab')

    @patch('psutil.cpu_percent')
    @patch('psutil.cpu_freq')
    @patch('psutil.virtual_memory')
    @patch('psutil.disk_usage')
    @patch('psutil.net_io_counters')
    @patch('psutil.net_if_addrs')
    @patch('psutil.net_if_stats')
    @patch.object(client, 'get_temperature')
    @patch.object(client, 'get_throttle_info')
    @patch.object(client, 'get_voltage_info')
    def test_collect_metrics_once(self, mock_voltage, mock_throttle,
                                  mock_temp, mock_net_stats, mock_net_addrs,
                                  mock_net_io, mock_disk, mock_mem,
                                  mock_cpu_freq, mock_cpu_percent):
        """Test collecting metrics."""
        # Mock return values for all the patched functions
        mock_cpu_percent.return_value = 50.0
        mock_cpu_freq.return_value = MagicMock(current=1000.0)
        mock_mem.return_value = MagicMock(total=4*1024**3, used=1*1024**3,
                                         available=3*1024**3, percent=25.0)
        mock_disk.return_value = MagicMock(total=100*1024**3, used=20*1024**3,
                                          free=80*1024**3)
        mock_net_io.return_value = MagicMock(bytes_sent=100, bytes_recv=200,
                                             packets_sent=10, packets_recv=20)
        mock_net_addrs.return_value = {}
        mock_net_stats.return_value = {}
        mock_temp.return_value = 45.0
        mock_throttle.return_value = '0x0'
        mock_voltage.return_value = {'core': 1.2}

        metrics = client.collect_metrics_once()

        self.assertEqual(metrics['cpu']['usage'], 50.0)
        self.assertEqual(metrics['memory']['percentage'], 25.0)
        self.assertEqual(metrics['temperature'], 45.0)

    @patch('requests.post')
    def test_send_data_success(self, mock_post):
        """Test sending data successfully."""
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        config = {'device_id': 'test-device', 'server_url': 'http://test-server'}
        metrics = {'cpu': {'usage': 50.0}}
        result = client.send_data(config, metrics)

        self.assertTrue(result)
        mock_post.assert_called_once()

    @patch('requests.post')
    def test_send_data_failure(self, mock_post):
        """Test sending data with a failure."""
        mock_post.side_effect = requests.exceptions.RequestException
        config = {'device_id': 'test-device', 'server_url': 'http://test-server'}
        metrics = {'cpu': {'usage': 50.0}}
        result = client.send_data(config, metrics)
        self.assertFalse(result)

    def test_cache_data(self):
        """Test caching data locally."""
        metrics = {'cpu': {'usage': 50.0}}
        client.cache_data(metrics)

        # Reset the mock connection state after the close() call
        self.mock_conn._closed = False
    
        c = self.mock_conn.cursor()
        c.execute("SELECT metrics_json FROM metrics_cache")
        row = c.fetchone()

        self.assertIsNotNone(row)
        self.assertEqual(json.loads(row[0]), metrics)

    @patch.object(client, 'send_data')
    def test_send_cached_data(self, mock_send_data):
        """Test sending cached data."""
        # Add some data to the cache
        metrics1 = {'cpu': {'usage': 50.0}}
        metrics2 = {'cpu': {'usage': 60.0}}
    
        client.cache_data(metrics1)
        # Reset the mock connection state
        self.mock_conn._closed = False
    
        client.cache_data(metrics2)
        # Reset the mock connection state
        self.mock_conn._closed = False

        # Mock send_data to always succeed
        mock_send_data.return_value = True
        config = {'device_id': 'test-device', 'server_url': 'http://test-server'}
        client.send_cached_data(config)

        # Check that the cache is empty
        self.mock_conn._closed = False
        c = self.mock_conn.cursor()
        c.execute("SELECT COUNT(*) FROM metrics_cache")
        count = c.fetchone()[0]
        self.assertEqual(count, 0)


if __name__ == '__main__':
    unittest.main()
