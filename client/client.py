"""Client code for Raspberry Pi status monitoring."""
import json
import os
import socket
import sqlite3
import subprocess
import time
import uuid

import psutil
import requests


SERVER_URL = 'http://localhost:5000'
if not SERVER_URL.startswith('http'):
    SERVER_URL = 'http://' + SERVER_URL
if not SERVER_URL.endswith(':5000') and not SERVER_URL.endswith(':5000/'):
    SERVER_URL = SERVER_URL.rstrip('/') + ':5000'

COLLECT_INTERVAL = 10  # seconds
BASE_PATH = os.path.dirname(os.path.abspath(__file__))
CLIENT_CONFIG_FILE = os.path.join(BASE_PATH, 'client_config.json')
LOCAL_DB_PATH = os.path.join(BASE_PATH, 'local_cache.db')


def read_client_config():
    """Read client configuration from file."""
    config = {}
    try:
        with open(CLIENT_CONFIG_FILE, 'r', encoding="UTF-8") as f:
            config = json.load(f)
    except FileNotFoundError:
        pass
    return config


config_data = read_client_config()
CLIENT_VERSION = config_data.get('version', '0.0.0')


def get_device_uid():
    """Generate a unique device ID from the MAC address."""
    mac = ':'.join(
        [f"{(uuid.getnode() >> i) & 0xff:02x}" for i in range(0, 8*6, 8)][::-1]
    )
    return mac


def get_hostname():
    """Get the system hostname."""
    try:
        return subprocess.check_output(['hostname']).decode('utf-8').strip()
    except Exception:
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
    if os.path.exists("/proc/device-tree/model"):
        with open("/proc/device-tree/model", "r", encoding="UTF-8") as f:
            model = f.read().lower()
            if all(("banana" in model,
                    os.path.exists('/sys/class/thermal/thermal_zone0/temp'))):
                with open(
                    '/sys/class/thermal/thermal_zone0/temp', 'r',
                    encoding="UTF-8"
                ) as f:
                    temp_str = f.read().strip()
                    return float(temp_str) / 1000.0

    try:
        cmd = ['vcgencmd', 'measure_temp']
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=True
        )
        temp_str = result.stdout.strip()
        temp = float(temp_str.replace('temp=', '').replace("'C", ''))
        return temp
    except (FileNotFoundError, subprocess.CalledProcessError):
        max_temp = 0
        if hasattr(psutil, 'sensors_temperatures'):
            temps = psutil.sensors_temperatures()
            if "coretemp" in temps:
                for entry in temps["coretemp"]:
                    max_temp = max(max_temp, entry.current)

        return max_temp


def get_throttle_info():
    """Get throttled status using vcgencmd."""
    throttled = None
    try:
        out = subprocess.run(
            ['vcgencmd', 'get_throttled'],
            capture_output=True,
            text=True,
            check=True
        )
        throttled = out.stdout.strip().split('=')[-1]
    except Exception:
        throttled = None

    return throttled


def get_voltage_info():
    """Get voltage information using vcgencmd or sysfs for Banana Pi."""
    voltages = {}

    if os.path.exists("/proc/device-tree/model"):
        with open("/proc/device-tree/model", "r", encoding="UTF-8") as f:
            model = f.read().lower()
            power_info_path = "/sys/devices/platform/soc/1c2ac00.i2c/i2c-1/1-0034/ac"
            if "banana" in model and os.path.exists(power_info_path):
                try:
                    with open(
                        f'{power_info_path}/amperage', 'r', encoding="UTF-8"
                    ) as f:
                        temp_str = f.read().strip()
                        current_amps = float(temp_str) / 1000.0
                        voltages["amperage"] = current_amps
                except Exception:
                    pass
                try:
                    with open(
                        f'{power_info_path}/voltage', 'r', encoding="UTF-8"
                    ) as f:
                        temp_str = f.read().strip()
                        current_volt = float(temp_str) / 1000000.0
                        voltages["core"] = current_volt
                except Exception:
                    pass
            else:
                try:
                    power_info_path = "/sys/class/power_supply/max17042/current_now"
                    if os.path.exists(power_info_path):
                        with open(power_info_path, 'r', encoding="UTF-8") as f:
                            amp_str = f.read().strip()
                            voltages["amperage"] = float(amp_str) / 1000000.0
                except Exception:
                    pass

                try:
                    for name in ('core', 'sdram_c', 'sdram_i', 'sdram_p'):
                        try:
                            out = subprocess.run(
                                ['vcgencmd', 'measure_volts', name],
                                capture_output=True,
                                text=True,
                                check=True
                            )
                            v = out.stdout.strip().split('=')[-1]
                            if v.endswith('V'):
                                v = v[:-1]
                            try:
                                voltages[name] = float(v)
                            except Exception:
                                voltages[name] = None
                        except Exception:
                            voltages[name] = None
                except Exception:
                    voltages = {}
    return voltages


def get_active_ifaces(net_io_ifaces, net_if_addrs, net_if_stats):
    """Get active network interfaces with stats."""
    active_ifaces = {}
    for iface, stats in net_io_ifaces.items():
        if (iface == 'lo' or stats.bytes_sent + stats.bytes_recv == 0 or
                iface.startswith(('veth', 'docker', 'br-'))):
            continue

        if_stats = net_if_stats.get(iface, None)
        is_up = if_stats.isup if if_stats else False

        if not is_up:
            continue

        iface_info = {
            'bytes_sent': stats.bytes_sent,
            'bytes_recv': stats.bytes_recv,
            'packets_sent': stats.packets_sent,
            'packets_recv': stats.packets_recv,
            'speed': if_stats.speed if if_stats else None,
            'is_up': is_up,
            'mtu': if_stats.mtu if if_stats else None,
        }

        addresses = net_if_addrs.get(iface, [])
        ips = [addr.address for addr in addresses
               if addr.family in {2, 10}]
        if ips:
            iface_info['addresses'] = ips

        active_ifaces[iface] = iface_info
    return active_ifaces


def collect_metrics_once():
    """Collect a one-off snapshot of system metrics."""

    cpu_usage = psutil.cpu_percent(interval=1)
    cpu_freq = psutil.cpu_freq()
    cpu_frequency = f"{cpu_freq.current:.2f} MHz" if cpu_freq else "N/A"

    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')

    net_io_total = psutil.net_io_counters()
    net_io_ifaces = psutil.net_io_counters(pernic=True)
    net_if_addrs = psutil.net_if_addrs()
    net_if_stats = psutil.net_if_stats()
    active_ifaces = get_active_ifaces(
        net_io_ifaces, net_if_addrs, net_if_stats
    )
    throttled = get_throttle_info()
    voltages = get_voltage_info()
    temperature = get_temperature()
    uptime = time.time() - psutil.boot_time()

    metrics = {
        'cpu': {'usage': cpu_usage, 'frequency': cpu_frequency},
        'memory': {
            'total': round(memory.total / (1024**3), 2),
            'used': round(memory.used / (1024**3), 2),
            'available': round(memory.available / (1024**3), 2),
            'percentage': memory.percent
        },
        'disk': {
            'total': round(disk.total / (1024**3), 2),
            'used': round(disk.used / (1024**3), 2),
            'free': round(disk.free / (1024**3), 2),
            'percentage': round((disk.used / disk.total) * 100, 2)
        },
        'network': {
            'total': {
                'bytes_sent': net_io_total.bytes_sent,
                'bytes_recv': net_io_total.bytes_recv,
                'packets_sent': net_io_total.packets_sent,
                'packets_recv': net_io_total.packets_recv
            },
            'interfaces': active_ifaces
        },
        'throttled': throttled,
        'voltages': voltages,
        'temperature': temperature,
        'uptime': uptime
    }
    return metrics


def load_config():
    """Load client configuration from file."""
    if not os.path.exists(CLIENT_CONFIG_FILE):
        return None
    try:
        with open(CLIENT_CONFIG_FILE, 'r', encoding="UTF-8") as f:
            config = json.load(f)
            if "device_id" not in config or "server_url" not in config:
                return None
            return config
    except (IOError, json.JSONDecodeError):
        return None


def save_config(config):
    """Save client configuration to file."""
    with open(CLIENT_CONFIG_FILE, 'w', encoding="UTF-8") as f:
        json.dump(config, f, indent=4)


def register_client():
    """Register this client with the server and save the config."""
    hostname = get_hostname()
    device_uid = get_device_uid()
    payload = {
        'hostname': hostname,
        'device_uid': device_uid,
        'device_name': hostname
    }
    headers = {'X-Client-Version': CLIENT_VERSION}

    try:
        response = requests.post(
            f"{SERVER_URL}/api/register", json=payload,
            headers=headers, timeout=10
        )
        response.raise_for_status()

        device_id = response.json().get('device_id')
        config_data.update({
            'device_id': device_id,
            'server_url': SERVER_URL,
            'device_uid': device_uid
        })
        save_config(config_data)

        print(f"Successfully registered with device_id: {device_id}")
        return config_data
    except requests.exceptions.RequestException as e:
        print(f"Error registering with server: {e}")
        return None


def send_data(config, metrics):
    """Send a single data point to the server."""
    payload = {
        'device_id': config['device_id'],
        'metrics': metrics
    }
    headers = {'X-Client-Version': CLIENT_VERSION}
    try:
        response = requests.post(
            f"{config['server_url']}/api/data", json=payload,
            headers=headers, timeout=10
        )
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        print(f"Could not send data to server: {e}")
        return False


def cache_data(metrics):
    """Save metrics to the local cache."""
    conn = sqlite3.connect(LOCAL_DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO metrics_cache (metrics_json) VALUES (?)",
        (json.dumps(metrics),)
    )
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
            c.execute("DELETE FROM metrics_cache WHERE id = ?", (row['id'],))
            conn.commit()
            print(f"Successfully sent cached record ID {row['id']}.")
        else:
            print("Server still unreachable. Stopping cache sending.")
            break
    conn.close()


def main():
    """Main loop for the client."""
    init_local_db()
    config = load_config()

    if not config:
        print("No configuration found. Attempting to register new client...")
        config = register_client()
        if not config:
            print("""
            Registration failed. Please check server URL and connectivity.
            Exiting.
            """)
            return

    while True:
        send_cached_data(config)

        print("Collecting new metrics...")
        metrics = collect_metrics_once()

        if not send_data(config, metrics):
            cache_data(metrics)

        time.sleep(COLLECT_INTERVAL)


if __name__ == '__main__':
    main()
