import sqlite3
import os

DB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    'system_stats.db'
)

def create_tables(conn=None):
    """
    Creates the necessary database tables if they don't exist.
    Can be passed an existing connection or will create a new one.
    """
    should_close = False
    if conn is None:
        conn = sqlite3.connect(DB_PATH)
        should_close = True
    
    c = conn.cursor()

    # Devices table
    c.execute('''CREATE TABLE IF NOT EXISTS devices (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 device_uid TEXT UNIQUE NOT NULL,
                 device_name TEXT,
                 hostname TEXT,
                 ip_address TEXT,
                 last_seen DATETIME
                 )''')

    # System stats table
    c.execute('''CREATE TABLE IF NOT EXISTS stats (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 device_id INTEGER,
                 timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                 cpu_usage REAL,
                 cpu_frequency TEXT,
                 memory_used REAL,
                 memory_total REAL,
                 memory_percentage REAL,
                 disk_used REAL,
                 disk_total REAL,
                 disk_percentage REAL,
                 temperature REAL,
                 uptime REAL,
                 throttled TEXT,
                 voltages TEXT,
                 FOREIGN KEY (device_id) REFERENCES devices (id)
                 )''')

    # Network stats table
    c.execute('''CREATE TABLE IF NOT EXISTS network_stats (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 stats_id INTEGER,
                 interface_name TEXT,
                 bytes_sent INTEGER,
                 bytes_recv INTEGER,
                 packets_sent INTEGER,
                 packets_recv INTEGER,
                 speed INTEGER,
                 mtu INTEGER,
                 is_up BOOLEAN,
                 addresses TEXT,
                 FOREIGN KEY (stats_id) REFERENCES stats (id)
                 )''')

    conn.commit()

    if should_close:
        conn.close()
        print("Created/verified tables in system_stats.db")


if __name__ == '__main__':
    create_tables()
