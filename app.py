#!/usr/bin/env python3
"""
Raspberry Pi Status Monitor - improved

Changes made:
- Background collector thread that periodically samples metrics and
    stores them in SQLite.
- In-memory cached latest metrics for fast API responses.
- DB schema expanded to include network stats.
"""

import threading
import time
import sqlite3
import subprocess

import psutil
from flask import Flask, render_template, jsonify


app = Flask(__name__)


DB_PATH = 'system_stats.db'
COLLECT_INTERVAL = 5


def init_db():
    """Initialize the SQLite database and create tables if missing."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS stats (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                 cpu_usage REAL,
                 cpu_frequency TEXT,
                 memory_used REAL,
                 memory_total REAL,
                 memory_percentage REAL,
                 disk_used REAL,
                 disk_total REAL,
                 disk_percentage REAL,
                 temperature REAL
                 )''')

    c.execute('''CREATE TABLE IF NOT EXISTS network_stats (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 stats_id INTEGER,
                 interface_name TEXT,
                 bytes_sent INTEGER,
                 bytes_recv INTEGER,
                 packets_sent INTEGER,
                 packets_recv INTEGER,
                 speed INTEGER,
                 FOREIGN KEY(stats_id) REFERENCES stats(id)
                 )''')
    conn.commit()
    conn.close()


def save_stats_to_db(stats):
    """Save a metrics snapshot to the DB with per-interface network stats."""
    conn = sqlite3.connect(DB_PATH)
    try:
        c = conn.cursor()

        c.execute('''INSERT INTO stats (
                    cpu_usage, cpu_frequency, memory_used, memory_total,
                    memory_percentage, disk_used, disk_total, disk_percentage,
                    temperature
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', (
            stats['cpu']['usage'],
            stats['cpu']['frequency'],
            stats['memory']['used'],
            stats['memory']['total'],
            stats['memory']['percentage'],
            stats['disk']['used'],
            stats['disk']['total'],
            stats['disk']['percentage'],
            stats['temperature']
        ))

        stats_id = c.lastrowid

        for iface, iface_stats in stats['network']['interfaces'].items():
            c.execute('''INSERT INTO network_stats (
                        stats_id, interface_name, bytes_sent, bytes_recv,
                        packets_sent, packets_recv, speed
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)''', (
                stats_id,
                iface,
                iface_stats['bytes_sent'],
                iface_stats['bytes_recv'],
                iface_stats['packets_sent'],
                iface_stats['packets_recv'],
                iface_stats['speed']
            ))

        conn.commit()
    finally:
        conn.close()


latest_metrics = {}
metrics_lock = threading.Lock()


def collect_metrics_once() -> dict:
    """Collect a one-off snapshot of system metrics."""

    cpu_usage = psutil.cpu_percent(interval=1)
    cpu_freq = psutil.cpu_freq()
    cpu_frequency = f"{cpu_freq.current:.2f} MHz" if cpu_freq else "N/A"

    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')

    net_io_total = psutil.net_io_counters()
    net_io_ifaces = psutil.net_io_counters(pernic=True)

    active_ifaces = {}
    for iface, stats in net_io_ifaces.items():
        if (
            iface != 'lo' and
            stats.bytes_sent + stats.bytes_recv > 0 and
            not iface.startswith('veth')
        ):
            active_ifaces[iface] = {
                'bytes_sent': stats.bytes_sent,
                'bytes_recv': stats.bytes_recv,
                'packets_sent': stats.packets_sent,
                'packets_recv': stats.packets_recv,
                'speed': None
            }
            try:
                import ethtool
                active_ifaces[iface]['speed'] = ethtool.get_speed(iface)
            except (ImportError, IOError):
                pass

    temperature = get_temperature()

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
        'temperature': temperature,
        'uptime': get_uptime()
    }

    return metrics


def collector_loop():
    """Background thread loop that collects metrics and persists them."""
    while True:
        try:
            metrics = collect_metrics_once()
            with metrics_lock:
                latest_metrics.clear()
                latest_metrics.update(metrics)

            try:
                save_stats_to_db(metrics)
            except Exception as e:
                app.logger.warning('Failed to save metrics to DB: %s', e)
        except Exception as e:
            app.logger.exception('Error in collector loop: %s', e)

        sleep_for = max(0, COLLECT_INTERVAL - 1)
        time.sleep(sleep_for)


def get_temperature():
    """Get CPU temperature (tries vcgencmd then psutil sensors)."""
    try:
        cmd = ['vcgencmd', 'measure_temp']
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        temp_str = result.stdout.strip()
        temp = float(
            temp_str.replace('temp=', '').replace("'C", '')
        )
        return temp
    except Exception:
        try:
            temps = psutil.sensors_temperatures()
            for key in ('cpu-thermal', 'coretemp', 'cpu_thermal'):
                if key in temps and temps[key]:
                    return float(temps[key][0].current)
        except Exception:
            pass
    return 0.0


def get_uptime() -> str:
    uptime_seconds = time.time() - psutil.boot_time()
    hours = int(uptime_seconds // 3600)
    minutes = int((uptime_seconds % 3600) // 60)
    return f"{hours} hours, {minutes} minutes"


@app.route('/')
def index():
    """Render initial page with latest metrics.

    Uses cached metrics if available for fast responses,
    falls back to collecting fresh metrics if needed.
    """
    with metrics_lock:
        if latest_metrics:
            system_info = latest_metrics.copy()
        else:
            system_info = collect_metrics_once()
    return render_template('index.html', system_info=system_info)


@app.route('/api/system-info')
def api_system_info():
    """Fast API returning the most recent cached metrics."""
    with metrics_lock:
        if latest_metrics:
            return jsonify(latest_metrics)

    metrics = collect_metrics_once()
    return jsonify(metrics)


@app.route('/api/history')
def api_history():
    """Return recent historical points for charting (most recent first)."""
    conn = sqlite3.connect(DB_PATH)
    try:
        c = conn.cursor()

        c.execute('''
            SELECT id, timestamp, cpu_usage, memory_percentage,
                   disk_percentage, temperature
            FROM stats
            ORDER BY timestamp DESC
            LIMIT 50
        ''')
        rows = c.fetchall()

        history = []
        for row in rows:

            c.execute('''
                SELECT interface_name, bytes_sent, bytes_recv,
                       packets_sent, packets_recv, speed
                FROM network_stats
                WHERE stats_id = ?
            ''', (row[0],))
            net_rows = c.fetchall()

            interfaces = {}
            for net_row in net_rows:
                interfaces[net_row[0]] = {
                    'bytes_sent': net_row[1],
                    'bytes_recv': net_row[2],
                    'packets_sent': net_row[3],
                    'packets_recv': net_row[4],
                    'speed': net_row[5]
                }

            history.append({
                'timestamp': row[1],
                'cpu_usage': row[2],
                'memory_percentage': row[3],
                'disk_percentage': row[4],
                'temperature': row[5],
                'network': interfaces
            })

        return jsonify(history)
    finally:
        conn.close()


def start_collector_thread():
    """Start the background metrics collection thread."""
    collector = threading.Thread(
        target=collector_loop,
        daemon=True,
        name='metrics-collector'
    )
    collector.start()


if __name__ == '__main__':
    init_db()
    start_collector_thread()
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True,
        threaded=True
    )
