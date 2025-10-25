#!/bin/bash

# This script installs the RPi Monitor Server component and sets it up as a systemd service.

# Ensure the script is run as root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root"
  exit 1
fi

echo "Starting RPi Monitor Server installation..."

# Define paths
# Assuming the script is run from the directory where it is located.
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
INSTALL_DIR="/opt/rpi-monitor-server"
SERVICE_NAME="rpi-monitor-server.service"
SERVICE_FILE_PATH="/etc/systemd/system/$SERVICE_NAME"
REQUIREMENTS_FILE="$SCRIPT_DIR/requirements.txt"
PROJECT_ROOT_DIR=$(dirname "$SCRIPT_DIR")

echo "Creating installation directory at $INSTALL_DIR..."
mkdir -p $INSTALL_DIR
# Copy server files and the central database files
echo "Copying application files..."
cp -r "$SCRIPT_DIR"/*.py "$INSTALL_DIR/"
cp -r "$SCRIPT_DIR"/static "$INSTALL_DIR/"
cp -r "$SCRIPT_DIR"/templates "$INSTALL_DIR/"
cp "$PROJECT_ROOT_DIR"/create_tables.py "$INSTALL_DIR/"
cp "$PROJECT_ROOT_DIR"/system_stats.db "$INSTALL_DIR/" 2>/dev/null || true # Copy db if it exists

echo "Installing Python dependencies..."
if [ -f "$REQUIREMENTS_FILE" ]; then
    pip3 install -r "$REQUIREMENTS_FILE"
else
    echo "WARNING: requirements.txt not found. Skipping dependency installation."
fi

echo "Creating systemd service file..."

# Create the service file content
# Note: WorkingDirectory is now the installation directory
SERVICE_CONTENT="[Unit]
Description=RPi Monitor Server
After=network.target

[Service]
User=root
Group=root
WorkingDirectory=$INSTALL_DIR
ExecStart=$(which python3) $INSTALL_DIR/server.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target"

echo "$SERVICE_CONTENT" > $SERVICE_FILE_PATH

echo "Enabling and starting the service..."
systemctl daemon-reload
systemctl enable $SERVICE_NAME
systemctl start $SERVICE_NAME

echo "-------------------------------------------------"
echo "Installation complete."
echo "The server is now running."
echo "You can check its status with: sudo systemctl status $SERVICE_NAME"
echo "The web interface should be accessible at http://<your-server-ip>:5000"
echo "-------------------------------------------------"

exit 0