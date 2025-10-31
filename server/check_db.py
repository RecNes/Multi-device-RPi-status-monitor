"""Script to check the contents of the system_stats.db database."""

import sqlite3
conn = sqlite3.connect('system_stats.db')
c = conn.cursor()
print(
    'Tables:', 
    c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
)

try:
    rows = c.execute(
        'SELECT id, timestamp FROM stats ORDER BY timestamp DESC LIMIT 3'
    ).fetchall()
    print('Recent stats rows:', rows)
except Exception as e:
    print('Error querying stats:', e)

try:
    rows = c.execute(
        '''SELECT id, stats_id, interface_name
        FROM network_stats
        ORDER BY id DESC
        LIMIT 3'''
    ).fetchall()
    print('Recent network rows:', rows)
except Exception as e:
    print('Error querying network_stats:', e)

conn.close()
