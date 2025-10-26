#!/usr/bin/env bash

# This script uninstalls the RPi Monitor application by reversing the steps
# from the install.sh script.

# Ensure the script is run as root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root"
  exit 1
fi

echo "=================================================="
echo "Raspberry Pi Web Monitoring App Uninstallation"
echo "=================================================="

# --- Define paths and names based on the install script ---
PROJECT_PATH=$(pwd) # Assuming the script is run from the project root
NGINX_CONF_NAME="rpi_monitor"
NGINX_CONF_DEST="/etc/nginx/sites-available/$NGINX_CONF_NAME"
NGINX_SYMLINK="/etc/nginx/sites-enabled/$NGINX_CONF_NAME"
SYSTEMD_SERVICE_NAME="rpi_monitor.service"
SYSTEMD_SERVICE_FILE="/etc/systemd/system/$SYSTEMD_SERVICE_NAME"
GUNICORN_SOCKET="/tmp/rpi_monitor.sock"

# 1. Stop and disable the Systemd service
echo "1. Stopping and disabling the Systemd service..."
if [ -f "$SYSTEMD_SERVICE_FILE" ]; then
    echo "  -> Stopping $SYSTEMD_SERVICE_NAME..."
    systemctl stop $SYSTEMD_SERVICE_NAME
    echo "  -> Disabling $SYSTEMD_SERVICE_NAME..."
    systemctl disable $SYSTEMD_SERVICE_NAME
    echo "  -> Removing service file..."
    rm "$SYSTEMD_SERVICE_FILE"
    echo "  -> Reloading Systemd daemon..."
    systemctl daemon-reload
else
    echo "  -> Service file not found. Skipping."
fi

# 2. Remove Nginx configuration
echo "2. Removing Nginx configuration..."
if [ -L "$NGINX_SYMLINK" ]; then
    echo "  -> Removing Nginx symlink: $NGINX_SYMLINK"
    rm "$NGINX_SYMLINK"
else
    echo "  -> Nginx symlink not found. Skipping."
fi

if [ -f "$NGINX_CONF_DEST" ]; then
    echo "  -> Removing Nginx config file: $NGINX_CONF_DEST"
    rm "$NGINX_CONF_DEST"
else
    echo "  -> Nginx config file not found. Skipping."
fi

# Restore default Nginx site if it exists in sites-available
if [ ! -e "/etc/nginx/sites-enabled/default" ] && [ -e "/etc/nginx/sites-available/default" ]; then
    echo "  -> Restoring default Nginx site..."
    ln -s "/etc/nginx/sites-available/default" "/etc/nginx/sites-enabled/default"
fi

echo "  -> Restarting Nginx to apply changes..."
systemctl restart nginx

# 3. Remove the Gunicorn socket file if it exists
echo "3. Cleaning up socket file..."
if [ -S "$GUNICORN_SOCKET" ]; then
    echo "  -> Removing Gunicorn socket file: $GUNICORN_SOCKET"
    rm "$GUNICORN_SOCKET"
else
    echo "  -> Socket file not found. Skipping."
fi

# The script does not remove the Python virtual environment,
# installed packages (apt), or the project files themselves.
# This is a safe default.

echo "=================================================="
echo "Uninstallation Complete!"
echo ""
echo "What was NOT removed:"
echo "  - The project directory ('$PROJECT_PATH')."
echo "  - The Python virtual environment ('venv')."
echo "  - System packages installed with apt (like nginx, python3, etc.)."
echo "=================================================="

exit 0