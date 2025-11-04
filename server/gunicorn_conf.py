"""Gunicorn configuration file for RPi Monitor Server"""
bind = "unix:/tmp/rpi_monitor.sock"
umask = 0o007
workers = 2
worker_class = "gthread"
threads = 4
timeout = 30
keepalive = 5
preload_app = True
max_requests = 1000
max_requests_jitter = 50
user = "root"
group = "www-data"
capture_output = True
accesslog = "/var/log/rpi-monitor-server.access"
errorlog = "/var/log/rpi-monitor-server.error"
loglevel = "info"
