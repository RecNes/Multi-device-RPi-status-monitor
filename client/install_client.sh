#!/bin/bash

# This script installs the RPi Monitor Client component and sets it up as a systemd service.

# Ensure the script is run as root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root"
  exit 1
fi

echo "Starting RPi Monitor Client installation..."

# Prompt for server URL
read -p "Enter the full URL of the RPi Monitor Server (e.g., http://192.168.1.100:5000): " SERVER_URL

if [ -z "$SERVER_URL" ]; then
    echo "Server URL cannot be empty. Aborting."
    exit 1
fi

echo "Server URL set to: $SERVER_URL"

# Define paths
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
INSTALL_DIR="/opt/rpi-monitor-client"
SERVICE_NAME="rpi-monitor-client.service"
SERVICE_FILE_PATH="/etc/systemd/system/$SERVICE_NAME"
REQUIREMENTS_FILE="$SCRIPT_DIR/requirements.txt"
CLIENT_PY_FILE="$INSTALL_DIR/client.py"

echo "Creating installation directory at $INSTALL_DIR..."
mkdir -p $INSTALL_DIR
cp "$SCRIPT_DIR"/*.py "$INSTALL_DIR/"

echo "Configuring server URL in client script..."
# Use sed to replace the placeholder URL. The '#' is used as a delimiter to avoid issues with slashes in the URL.
sed -i "s#^SERVER_URL = .*#SERVER_URL = '$SERVER_URL'#" "$CLIENT_PY_FILE"

echo "Installing Python dependencies..."
if [ -f "$REQUIREMENTS_FILE" ]; then
    pip3 install -r "$REQUIREMENTS_FILE"
else
    echo "WARNING: requirements.txt not found. Skipping dependency installation."
fi

echo "Creating systemd service file..."

# Create the service file content
SERVICE_CONTENT="[Unit]
Description=RPi Monitor Client
After=network.target

[Service]
User=root
Group=root
WorkingDirectory=$INSTALL_DIR
ExecStart=$(which python3) $CLIENT_PY_FILE
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target"

echo "$SERVICE_CONTENT" > $SERVICE_FILE_PATH

echo "Enabling and starting the service..."
systemctl daemon-reload
systemctl enable $SERVICE_NAME
systemctl start $SERVICE_NAME

echo "-------------------------------------------------"
echo "Installation complete."
echo "The client is now running and will report to $SERVER_URL."
echo "You can check its status with: sudo systemctl status $SERVICE_NAME"
echo "-------------------------------------------------"

exit 0