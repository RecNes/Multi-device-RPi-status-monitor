#!/bin/bash

# This script uninstalls the RPi Monitor Client component.

if [ "$EUID" -ne 0 ]; then
  echo "Please run as root"
  exit 1
fi

echo "Starting RPi Monitor Client uninstallation..."

INSTALL_DIR="/opt/rpi-monitor-client"
SERVICE_NAME="rpi-monitor-client.service"
SERVICE_FILE_PATH="/etc/systemd/system/$SERVICE_NAME"

if [ -f "$SERVICE_FILE_PATH" ]; then
    echo "Stopping and disabling the systemd service..."
    systemctl stop $SERVICE_NAME
    systemctl disable $SERVICE_NAME
    rm "$SERVICE_FILE_PATH"
    echo "Reloading systemd daemon..."
    systemctl daemon-reload
else
    echo "Service file not found. Skipping service removal."
fi

if [ -d "$INSTALL_DIR" ]; then
    echo "Removing installation directory at $INSTALL_DIR..."
    rm -rf "$INSTALL_DIR"
else
    echo "Installation directory not found. Skipping directory removal."
fi

echo "-------------------------------------------------"
echo "Uninstallation complete."
echo "-------------------------------------------------"

exit 0
