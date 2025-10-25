import requests
import time
import sqlite3
import subprocess
import psutil
import uuid
import json
import os

# This will be configured during installation
SERVER_URL = 'http://localhost:5000'
COLLECT_INTERVAL = 10 # seconds
CLIENT_CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'client_config.json')
LOCAL_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'local_cache.db')

def get_device_uid():
    """Generate a unique device ID from the MAC address."""
    mac = ':'.join(['{:02x}'.format((uuid.getnode() >> i) & 0xff) for i in range(0,8*6,8)][::-1])
    return mac

def get_hostname():
    """Get the system hostname."""
    try:
        return subprocess.check_output(['hostname']).decode('utf-8').strip()
    except Exception:
        import socket
        return socket.gethostname()

def init_local_db():
    """Initialize the local SQLite database for caching."""
    conn = sqlite3.connect(LOCAL_DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS metrics_cache (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                 metrics_json TEXT
                 )''')
    conn.commit()
    conn.close()

def get_temperature():
    """Get CPU temperature (tries vcgencmd then psutil sensors)."""
    try:
        cmd = ['vcgencmd', 'measure_temp']
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        temp_str = result.stdout.strip()
        temp = float(temp_str.replace('temp=', '').replace("'C", ''))
        return temp
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass # vcgencmd not available

    try:
        if hasattr(psutil, 'sensors_temperatures'):
            temps = psutil.sensors_temperatures()
            if temps:
                for key in ('cpu-thermal', 'coretemp', 'cpu_thermal', 'k10temp'):
                    if key in temps and temps[key]:
                        return float(temps[key][0].current)
    except Exception:
        pass

    return 0.0

def collect_metrics_once():
    """Collect a one-off snapshot of system metrics."""
    cpu_usage = psutil.cpu_percent(interval=1)
    cpu_freq = psutil.cpu_freq()
    cpu_frequency = f"{cpu_freq.current:.2f} MHz" if cpu_freq else "N/A"
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')

    metrics = {
        'cpu': {'usage': cpu_usage, 'frequency': cpu_frequency},
        'memory': {
            'total': round(memory.total / (1024**3), 2),
            'used': round(memory.used / (1024**3), 2),
            'percentage': memory.percent
        },
        'disk': {
            'total': round(disk.total / (1024**3), 2),
            'used': round(disk.used / (1024**3), 2),
            'percentage': round((disk.used / disk.total) * 100, 2)
        },
        'temperature': get_temperature(),
        'uptime': time.time() - psutil.boot_time()
    }
    return metrics

def load_config():
    """Load client configuration from file."""
    if not os.path.exists(CLIENT_CONFIG_FILE):
        return None
    try:
        with open(CLIENT_CONFIG_FILE, 'r') as f:
            return json.load(f)
    except (IOError, json.JSONDecodeError):
        return None

def save_config(config):
    """Save client configuration to file."""
    with open(CLIENT_CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

def register_client():
    """Register this client with the server and save the config."""
    hostname = get_hostname()
    device_uid = get_device_uid()
    payload = {'hostname': hostname, 'device_uid': device_uid, 'device_name': hostname}

    try:
        print(f"Attempting to register with server at {SERVER_URL}...")
        response = requests.post(f"{SERVER_URL}/api/register", json=payload, timeout=10)
        response.raise_for_status()

        device_id = response.json().get('device_id')
        config = {'device_id': device_id, 'server_url': SERVER_URL, 'device_uid': device_uid}
        save_config(config)

        print(f"Successfully registered with device_id: {device_id}")
        return config
    except requests.exceptions.RequestException as e:
        print(f"Error registering with server: {e}")
        return None

def send_data(config, metrics):
    """Send a single data point to the server."""
    payload = {
        'device_id': config['device_id'],
        'metrics': metrics
    }
    try:
        response = requests.post(f"{config['server_url']}/api/data", json=payload, timeout=10)
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        print(f"Could not send data to server: {e}")
        return False

def cache_data(metrics):
    """Save metrics to the local cache."""
    conn = sqlite3.connect(LOCAL_DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO metrics_cache (metrics_json) VALUES (?)", (json.dumps(metrics),))
    conn.commit()
    conn.close()
    print("Data cached locally.")

def send_cached_data(config):
    """Send all cached data to the server and clear cache on success."""
    conn = sqlite3.connect(LOCAL_DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT id, metrics_json FROM metrics_cache ORDER BY id")
    rows = c.fetchall()

    if not rows:
        conn.close()
        return

    print(f"Found {len(rows)} cached records. Attempting to send...")

    for row in rows:
        metrics = json.loads(row['metrics_json'])
        if send_data(config, metrics):
            # Delete from cache only if successfully sent
            c.execute("DELETE FROM metrics_cache WHERE id = ?", (row['id'],))
            conn.commit()
            print(f"Successfully sent cached record ID {row['id']}.")
        else:
            # Stop if server is not reachable
            print("Server still unreachable. Stopping cache sending.")
            break
    conn.close()

def main():
    init_local_db()
    config = load_config()

    if not config:
        print("No configuration found. Attempting to register new client...")
        config = register_client()
        if not config:
            print("Registration failed. Please check server URL and connectivity. Exiting.")
            return

    while True:
        # First, try to send any cached data
        send_cached_data(config)

        # Collect new data
        print("Collecting new metrics...")
        metrics = collect_metrics_once()

        # Try to send new data
        if not send_data(config, metrics):
            # If it fails, cache it
            cache_data(metrics)

        time.sleep(COLLECT_INTERVAL)

if __name__ == '__main__':
    main()
