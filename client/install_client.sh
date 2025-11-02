#!/bin/bash

# This script installs the RPi Monitor Client component and sets it up as a systemd service.

if [ "$EUID" -ne 0 ]; then
  echo "Please run as root"
  exit 1
fi

echo "Starting RPi Monitor Client installation..."
echo " "
# Prompt for server URL
read -p "Enter the full URL of the RPi Monitor Server (e.g., http://192.168.1.100:5000): " SERVER_URL

if [ -z "$SERVER_URL" ]; then
    echo "Server URL cannot be empty. Aborting."
    exit 1
fi

echo "Server URL set to: $SERVER_URL"
echo " "
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
sed -i "s#^SERVER_URL = .*#SERVER_URL = '$SERVER_URL'#" "$CLIENT_PY_FILE"


command_exists() {
    command -v "$1" >/dev/null 2>&1
}
echo " "
if command_exists apt-get; then
    if ! dpkg -s python3-venv >/dev/null 2>&1; then
        echo "python3-venv not found. Attempting to install..."
        echo " "
        apt-get update && apt-get install -y python3-venv gcc python3-dev
    fi
elif command_exists yum; then
    if ! rpm -q python3-virtualenv >/dev/null 2>&1; then
        echo "python3-virtualenv not found. Attempting to install..."
        echo " "
        yum install -y python3-virtualenv
    fi
fi

if [ ! -d "$INSTALL_DIR/venv" ]; then
    echo "Attempting to create a Python virtual environment..."
    echo " "
    python3 -m venv "$INSTALL_DIR/venv"
fi

if [ ! -f "$INSTALL_DIR/venv/bin/python" ]; then
    echo "Error: Python virtual environment creation failed."
    echo "Please ensure 'python3-venv' is installed and try"
    echo "this command: python3 -m venv '$INSTALL_DIR/venv'"
    exit 1
else
    echo "Python virtual environment is already set."
fi

echo "Installing Python dependencies into virtual environment..."
if [ -f "$REQUIREMENTS_FILE" ]; then
    "$INSTALL_DIR/venv/bin/pip" install -r "$REQUIREMENTS_FILE"
else
    echo "WARNING: requirements.txt not found. Skipping dependency installation."
fi

echo " "
if [ -f "$SERVICE_FILE_PATH" ]; then
    echo "Updating $SERVICE_NAME systemd service file..."
else
    echo "Creating $SERVICE_NAME systemd service file..."
fi

SERVICE_CONTENT="[Unit]
Description=RPi Monitor Client
After=network.target

[Service]
User=root
Group=root
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/python $CLIENT_PY_FILE
StandardOutput=append:/var/log/rpi-monitor-client.log
StandardError=append:/var/log/rpi-monitor-client.log
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target"

echo "$SERVICE_CONTENT" > $SERVICE_FILE_PATH

echo "Enabling and starting the service..."
systemctl daemon-reload
if [ -f "$SERVICE_FILE_PATH" ]; then
    echo "Restarting service..."
    systemctl restart "$SERVICE_NAME"
else
    echo "Enabling and starting services..."
    systemctl enable "$SERVICE_NAME"
    systemctl start "$SERVICE_NAME"
fi

echo " "
echo "-------------------------------------------------"
echo "Installation complete."
echo "The client is now running and will report to $SERVER_URL."
echo "You can check its status with: sudo systemctl status $SERVICE_NAME"
echo "-------------------------------------------------"

exit 0