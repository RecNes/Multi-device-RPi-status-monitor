#!/usr/bin/env python3
"""
Raspberry Pi Status Monitor - Server

Receives data from multiple clients, stores it in SQLite,
and serves a web interface to view the data.
"""
import json
import os
import sqlite3
import threading
import time
from datetime import datetime, timezone, timedelta

from flask import Flask, render_template, jsonify, request

app = Flask(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'system_stats.db')
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'server_config.json')

# --- Version ---
try:
    with open(CONFIG_PATH, 'r') as f:
        config = json.load(f)
        SERVER_VERSION = config.get('version', '0.0.0')
except FileNotFoundError:
    SERVER_VERSION = '0.0.0'
# ------------------------------------

# --- Database Cleanup Configuration ---
STATS_RETENTION_DAYS = 30
INACTIVE_DEVICE_DAYS = 7
# ------------------------------------

def get_db_conn():
    """Get a database connection."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


@app.route('/')
def index():
    """Render the main dashboard page."""
    return render_template('index.html', server_version=SERVER_VERSION)


@app.route('/api/version', methods=['GET'])
def get_version():
    """Return the server version."""
    return jsonify({'version': SERVER_VERSION})


@app.route('/api/devices', methods=['GET'])
def get_devices():
    """Return a list of all registered devices."""
    conn = get_db_conn()
    devices = conn.execute('SELECT * FROM devices ORDER BY last_seen DESC').fetchall()
    devices_list = [dict(row) for row in devices]
    return jsonify(devices_list)


@app.route('/api/register', methods=['POST'])
def register_device():
    """Register a new device or update an existing one."""
    client_version = request.headers.get('X-Client-Version')
    if not client_version or client_version != SERVER_VERSION:
        return jsonify({
            'error': 'Client version mismatch',
            'client_version': client_version,
            'server_version': SERVER_VERSION
        }), 426

    data = request.get_json()
    if not data or 'device_uid' not in data:
        return jsonify({'error': 'device_uid is required'}), 400

    device_uid = data['device_uid']
    device_name = data.get('device_name', 'Unnamed Device')
    hostname = data.get('hostname')
    ip_address = request.remote_addr
    now = datetime.now(timezone.utc)

    conn = get_db_conn()
    cursor = conn.cursor()

    cursor.execute('SELECT id FROM devices WHERE device_uid = ?', (device_uid,))
    device = cursor.fetchone()

    if device:
        device_id = device['id']
        cursor.execute('''
            UPDATE devices
            SET device_name = ?, ip_address = ?, hostname = ?, last_seen = ?
            WHERE id = ?
        ''', (device_name, ip_address, hostname, now, device_id))
        conn.commit()
    else:
        cursor.execute('''
            INSERT INTO devices (device_uid, device_name, ip_address, hostname, last_seen)
            VALUES (?, ?, ?, ?, ?)
        ''', (device_uid, device_name, ip_address, hostname, now))
        device_id = cursor.lastrowid
        conn.commit()

    return jsonify({'status': 'success', 'device_id': device_id}), 200 if not device else 201


@app.route('/api/data', methods=['POST'])
def receive_data():
    """Receive and store metrics from a client."""
    client_version = request.headers.get('X-Client-Version')
    if not client_version or client_version != SERVER_VERSION:
        return jsonify({
            'error': 'Client version mismatch',
            'client_version': client_version,
            'server_version': SERVER_VERSION
        }), 426

    data = request.get_json()

    if not data or 'device_id' not in data or 'metrics' not in data:
        return jsonify({'error': 'device_id and metrics are required'}), 400

    device_id = data['device_id']
    metrics = data['metrics']

    conn = get_db_conn()
    cursor = conn.cursor()

    try:
        # Verify device_id exists
        cursor.execute('SELECT id FROM devices WHERE id = ?', (device_id,))
        if not cursor.fetchone():
            return jsonify({'error': 'Device not registered'}), 404

        cursor.execute('''INSERT INTO stats (
                    device_id, cpu_usage, cpu_frequency, memory_used, memory_total,
                    memory_percentage, disk_used, disk_total, disk_percentage,
                    temperature, uptime, throttled, voltages
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', (
            device_id,
            metrics['cpu']['usage'],
            metrics['cpu']['frequency'],
            metrics['memory']['used'],
            metrics['memory']['total'],
            metrics['memory']['percentage'],
            metrics['disk']['used'],
            metrics['disk']['total'],
            metrics['disk']['percentage'],
            metrics.get('temperature', 0.0),
            metrics.get('uptime', 0.0),
            metrics.get('throttled'),
            json.dumps(metrics.get('voltages', {})),
        ))

        stats_id = cursor.lastrowid

        for iface, iface_stats in metrics['network']['interfaces'].items():
            cursor.execute('''INSERT INTO network_stats (
                        stats_id, interface_name, bytes_sent, bytes_recv,
                        packets_sent, packets_recv, speed, mtu, is_up,
                        addresses
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', (
                stats_id,
                iface,
                iface_stats['bytes_sent'],
                iface_stats['bytes_recv'],
                iface_stats['packets_sent'],
                iface_stats['packets_recv'],
                iface_stats['speed'],
                iface_stats['mtu'],
                iface_stats['is_up'],
                json.dumps(iface_stats.get('addresses', []))
            ))

        cursor.execute('UPDATE devices SET last_seen = ? WHERE id = ?', (datetime.now(timezone.utc), device_id))

        conn.commit()
    except sqlite3.Error as e:
        conn.rollback()
        return jsonify({'error': f'Database error: {e}'}), 500


    return jsonify({'status': 'success'}), 201


@app.route('/api/history/<int:device_id>')
def api_history(device_id):
    """Return recent historical points for a specific device."""
    conn = get_db_conn()
    c = conn.cursor()

    try:
        c.execute('''
            SELECT timestamp, cpu_usage, memory_percentage,
                   disk_percentage, temperature
            FROM stats
            WHERE device_id = ?
            ORDER BY timestamp DESC
            LIMIT 100
        ''', (device_id,))
        rows = c.fetchall()
    except:
        rows = []

    history = [dict(row) for row in rows]
    return jsonify(history)


@app.route('/api/latest/<int:device_id>')
def api_latest(device_id):
    """Return the latest metrics for a specific device."""
    conn = get_db_conn()
    c = conn.cursor()

    try:
        c.execute('''
            SELECT s.*, d.device_name, d.hostname, d.ip_address
            FROM stats s
            JOIN devices d ON s.device_id = d.id
            WHERE s.device_id = ?
            ORDER BY s.timestamp DESC
            LIMIT 1
        ''', (device_id,))
        latest = c.fetchone()

        if not latest:
            return jsonify({'error': 'No data for this device'}), 404

        latest_dict = dict(latest)

        # Also fetch network stats for this entry
        c.execute('''
            SELECT interface_name, bytes_sent, bytes_recv, packets_sent, packets_recv, speed
            FROM network_stats
            WHERE stats_id = ?
        ''', (latest_dict['id'],))
        network_rows = c.fetchall()
        network_stats = {row['interface_name']: dict(row) for row in network_rows}
        latest_dict['network_stats'] = network_stats

        return jsonify(latest_dict)
    except sqlite3.Error:
        # If any database error occurs, return a 500 error.
        return jsonify({'error': 'Database error occurred'}), 500

# --- Database Cleanup Functions ---

def prune_old_stats(conn):
    """Delete stats and related network_stats older than STATS_RETENTION_DAYS."""
    try:
        c = conn.cursor()
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=STATS_RETENTION_DAYS)
        
        app.logger.info(f"Pruning records older than {STATS_RETENTION_DAYS} days (before {cutoff_date.strftime('%Y-%m-%d')})...")

        c.execute("DELETE FROM network_stats WHERE stats_id IN (SELECT id FROM stats WHERE timestamp < ?)", (cutoff_date,))
        deleted_net_stats = c.rowcount
        
        c.execute("DELETE FROM stats WHERE timestamp < ?", (cutoff_date,))
        deleted_stats = c.rowcount

        conn.commit()
        app.logger.info(f"Pruned {deleted_stats} records from 'stats' and {deleted_net_stats} records from 'network_stats'.")

    except sqlite3.Error as e:
        app.logger.error(f"An error occurred while pruning old stats: {e}")
        conn.rollback()

def prune_inactive_devices(conn):
    """Delete devices and all their data if they haven't been seen in INACTIVE_DEVICE_DAYS."""
    try:
        c = conn.cursor()
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=INACTIVE_DEVICE_DAYS)

        app.logger.info(f"Pruning devices inactive for {INACTIVE_DEVICE_DAYS} days (last seen before {cutoff_date.strftime('%Y-%m-%d %H:%M:%S')} UTC)...")

        c.execute("SELECT id, device_name FROM devices WHERE last_seen < ?", (cutoff_date,))
        inactive_devices = c.fetchall()

        if not inactive_devices:
            app.logger.info("No inactive devices found to prune.")
            return

        inactive_ids = [row['id'] for row in inactive_devices]
        placeholders = ','.join('?' for _ in inactive_ids)

        c.execute(f"DELETE FROM network_stats WHERE stats_id IN (SELECT id FROM stats WHERE device_id IN ({placeholders}))", inactive_ids)
        c.execute(f"DELETE FROM stats WHERE device_id IN ({placeholders})", inactive_ids)
        c.execute(f"DELETE FROM devices WHERE id IN ({placeholders})", inactive_ids)
        
        conn.commit()
        app.logger.info(f"Successfully pruned {len(inactive_ids)} inactive device(s).")

    except sqlite3.Error as e:
        app.logger.error(f"An error occurred while pruning inactive devices: {e}")
        conn.rollback()

def cleanup_loop():
    """Endless loop that runs cleanup tasks periodically."""
    while True:
        app.logger.info("DB cleanup thread waking up.")
        conn = get_db_conn()
        if conn:
            try:
                prune_old_stats(conn)
                prune_inactive_devices(conn)
            finally:
                conn.close()

        # Sleep for 24 hours
        time.sleep(24 * 60 * 60)

def start_cleanup_thread():
    """Start the background cleanup thread."""
    cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
    cleanup_thread.start()
    print("Started background DB cleanup thread.")

if __name__ == '__main__':
    # The init_db logic is now in create_tables.py and should be run manually.
    start_cleanup_thread()
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=False,
        threaded=True
    )
