import sqlite3
DB_PATH = 'system_stats.db'
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

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
             FOREIGN KEY(device_id) REFERENCES devices(id)
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
             mtu INTEGER,
             is_up BOOLEAN,
             addresses TEXT,
             FOREIGN KEY(stats_id) REFERENCES stats(id)
             )''')

c.execute('''CREATE TABLE IF NOT EXISTS devices (
             id INTEGER PRIMARY KEY AUTOINCREMENT,
             device_uid TEXT NOT NULL UNIQUE,
             device_name TEXT,
             ip_address TEXT,
             hostname TEXT,
             last_seen DATETIME
             )''')

conn.commit()
conn.close()
print('Created/verified tables in', DB_PATH)
