#!/bin/bash

# This script uninstalls the RPi Monitor Server component.

if [ "$EUID" -ne 0 ]; then
  echo "Please run as root"
  exit 1
fi

echo "Starting RPi Monitor Server uninstallation..."

INSTALL_DIR="/opt/rpi-monitor-server"
SERVICE_NAME="rpi-monitor-server.service"
SERVICE_FILE_PATH="/etc/systemd/system/$SERVICE_NAME"

if [ -f "$SERVICE_FILE_PATH" ]; then
    echo "Stopping and disabling the Gunicorn systemd service..."
    systemctl stop $SERVICE_NAME
    systemctl disable $SERVICE_NAME
    rm "$SERVICE_FILE_PATH"
    echo "Reloading systemd daemon..."
    systemctl daemon-reload
else
    echo "Gunicorn service file not found. Skipping service removal."
fi

echo "Removing web server configurations..."

LIGHTTPD_CONFIG="/etc/lighttpd/conf-enabled/10-rpi_monitor.conf"
if [ -f "$LIGHTTPD_CONFIG" ]; then
    echo "Found lighttpd configuration. Removing..."
    rm -f "$LIGHTTPD_CONFIG"
    rm -f "/etc/lighttpd/conf-available/10-rpi_monitor.conf"
    echo "Restarting lighttpd..."
    systemctl restart lighttpd
fi

NGINX_CONFIG_SYMLINK="/etc/nginx/sites-enabled/rpi_monitor"
NGINX_CONFIG_AVAILABLE="/etc/nginx/sites-available/rpi_monitor"
NGINX_CONFIG_CONF_D="/etc/nginx/conf.d/rpi_monitor.conf"

if [ -f "$NGINX_CONFIG_SYMLINK" ]; then
    echo "Found Nginx configuration (sites-enabled). Removing..."
    rm -f "$NGINX_CONFIG_SYMLINK"
    rm -f "$NGINX_CONFIG_AVAILABLE"
    if [ -f "/etc/nginx/sites-available/default" ]; then
        ln -sfn "/etc/nginx/sites-available/default" "/etc/nginx/sites-enabled/default"
    fi
    echo "Restarting Nginx..."
    systemctl restart nginx
elif [ -f "$NGINX_CONFIG_CONF_D" ]; then
    echo "Found Nginx configuration (conf.d). Removing..."
    rm -f "$NGINX_CONFIG_CONF_D"
    echo "Restarting Nginx..."
    systemctl restart nginx
fi

if [ -d "$INSTALL_DIR" ]; then
    echo "Removing installation directory at $INSTALL_DIR..."
    rm -rf "$INSTALL_DIR"
else
    echo "Installation directory not found. Skipping directory removal."
fi

echo "-------------------------------------------------"
echo "Uninstallation complete."
echo "The web server (lighttpd or Nginx) was not removed."
echo "-------------------------------------------------"

exit 0
