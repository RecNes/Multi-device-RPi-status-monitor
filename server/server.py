#!/usr/bin/env python3
"""
Raspberry Pi Status Monitor - Server

Receives data from multiple clients, stores it in SQLite,
and serves a web interface to view the data.
"""
import json
import os
import sqlite3
from datetime import datetime, timezone

from flask import Flask, render_template, jsonify, request

app = Flask(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'system_stats.db')
# Retention in days for historical records. Default 30 (about 1 month).
# Can be overridden by setting environment variable RETENTION_DAYS.
RETENTION_DAYS = int(os.environ.get('RETENTION_DAYS', '30'))


def get_db_conn():
    """Get a database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@app.route('/')
def index():
    """Render the main dashboard page."""
    return render_template('index.html')


@app.route('/api/devices', methods=['GET'])
def get_devices():
    """Return a list of all registered devices."""
    conn = get_db_conn()
    devices = conn.execute('SELECT * FROM devices ORDER BY last_seen DESC').fetchall()
    conn.close()
    devices_list = [dict(row) for row in devices]
    return jsonify(devices_list)


@app.route('/api/register', methods=['POST'])
def register_device():
    """Register a new device or update an existing one."""
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
        # print(f"Device {device_id} ({device_name}) checked in.")
    else:
        cursor.execute('''
            INSERT INTO devices (device_uid, device_name, ip_address, hostname, last_seen)
            VALUES (?, ?, ?, ?, ?)
        ''', (device_uid, device_name, ip_address, hostname, now))
        device_id = cursor.lastrowid
        conn.commit()
        # print(f"New device registered: ID {device_id} ({device_name})")

    conn.close()
    return jsonify({'status': 'success', 'device_id': device_id}), 200 if not device else 201


@app.route('/api/data', methods=['POST'])
def receive_data():
    """Receive and store metrics from a client."""
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
                    temperature, uptime
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', (
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
            metrics.get('uptime', 0.0)
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
    finally:
        conn.close()

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
    finally:
        conn.close()

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
    except:
        latest = []
    finally:
        conn.close()

    if not latest:
        return jsonify({'error': 'No data for this device'}), 404

    return jsonify(dict(latest))


if __name__ == '__main__':
    # The init_db logic is now in create_tables.py and should be run manually.
    app.run(
        host='0.0.0.0',
        port=5001,
        debug=True
    )
