#!/bin/bash

# This script installs the RPi Monitor Server component and sets it up as a systemd service.

if [ "$EUID" -ne 0 ]; then
  echo "Please run as root"
  exit 1
fi

echo "Starting RPi Monitor Server installation..."

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
INSTALL_DIR="/opt/rpi-monitor-server"
SERVICE_NAME="rpi-monitor-server.service"
SERVICE_FILE_PATH="/etc/systemd/system/$SERVICE_NAME"
REQUIREMENTS_FILE="$INSTALL_DIR/requirements.txt"
PROJECT_ROOT_DIR=$(dirname "$SCRIPT_DIR")

echo "Creating installation directory at $INSTALL_DIR..."
mkdir -p $INSTALL_DIR

echo "Copying application files..."
cp -r "$SCRIPT_DIR"/* "$INSTALL_DIR/"

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

if command_exists apt-get; then
    if ! dpkg -s python3-venv >/dev/null 2>&1; then
        echo "python3-venv not found. Attempting to install..."
        apt-get update && apt-get install -y python3-venv gcc python3-dev
    fi
elif command_exists yum; then
    if ! rpm -q python3-virtualenv >/dev/null 2>&1; then
        echo "python3-virtualenv not found. Attempting to install..."
        yum install -y python3-virtualenv
    fi
fi

echo "Creating Python virtual environment..."
python3 -m venv "$INSTALL_DIR/venv"

if [ ! -f "$INSTALL_DIR/venv/bin/python" ]; then
    echo "Error: Python virtual environment creation failed."
    echo "Please ensure 'python3-venv' is installed and try again."
    exit 1
fi

echo "Installing Python dependencies and Gunicorn..."
if [ -f "$REQUIREMENTS_FILE" ]; then
    "$INSTALL_DIR/venv/bin/pip" install -r "$REQUIREMENTS_FILE"
    "$INSTALL_DIR/venv/bin/pip" install gunicorn
else
    echo "WARNING: requirements.txt not found. Skipping dependency installation."
fi

echo "Initializing database..."
(cd "$INSTALL_DIR" && venv/bin/python create_tables.py)

WEBSERVER=""

if command_exists lighttpd; then
    echo "lighttpd is already installed. Using it."
    WEBSERVER="lighttpd"
elif command_exists nginx; then
    echo "nginx is already installed. Using it."
    WEBSERVER="nginx"
fi

if [ -z "$WEBSERVER" ]; then
    echo "No web server found. Attempting to install lighttpd..."
    if command_exists apt-get; then
        apt-get update && apt-get install -y lighttpd
        if command_exists lighttpd; then
            WEBSERVER="lighttpd"
        fi
    elif command_exists yum; then
        yum install -y lighttpd
        if command_exists lighttpd; then
            WEBSERVER="lighttpd"
        fi
    fi

    if [ -z "$WEBSERVER" ]; then
        echo "lighttpd installation failed or not supported. Attempting to install nginx..."
        if command_exists apt-get; then
            apt-get update && apt-get install -y nginx
            if command_exists nginx; then
                WEBSERVER="nginx"
            fi
        elif command_exists yum; then
            yum install -y nginx
            if command_exists nginx; then
                WEBSERVER="nginx"
            fi
        fi
    fi
fi

if [ -z "$WEBSERVER" ]; then
    echo "Error: Could not install a web server (lighttpd or nginx)."
    exit 1
fi

echo "Using $WEBSERVER as the web server."

if [ "$WEBSERVER" = "lighttpd" ]; then
    echo "Configuring lighttpd..."
    LIGHTTPD_CONFIG_SRC="$INSTALL_DIR/rpi_monitor.lighttpd"
    LIGHTTPD_CONFIG_DEST="/etc/lighttpd/conf-available/10-rpi_monitor.conf"
    
    cp "$LIGHTTPD_CONFIG_SRC" "$LIGHTTPD_CONFIG_DEST"
    ln -sfn "$LIGHTTPD_CONFIG_DEST" "/etc/lighttpd/conf-enabled/10-rpi_monitor.conf"
    
    lighty-enable-mod proxy
    
    systemctl restart lighttpd
else
    echo "Configuring Nginx..."

    NGINX_CONFIG_SRC="$INSTALL_DIR/rpi_monitor.nginx"
    NGINX_CONFIG_DEST="/etc/nginx/sites-available/rpi_monitor"
    NGINX_SYMLINK="/etc/nginx/sites-enabled/rpi_monitor"

    if [ ! -d "/etc/nginx/sites-available" ]; then
        NGINX_CONFIG_DEST="/etc/nginx/conf.d/rpi_monitor.conf"
        NGINX_SYMLINK=""
    fi

    cp "$NGINX_CONFIG_SRC" "$NGINX_CONFIG_DEST"
    sed -i "s|alias /home/pi/rpi_monitor_app/static;|alias $INSTALL_DIR/static;|" "$NGINX_CONFIG_DEST"

    if [ -n "$NGINX_SYMLINK" ]; then
      # rm -f /etc/nginx/sites-enabled/default
      ln -sfn "$NGINX_CONFIG_DEST" "$NGINX_SYMLINK"
    fi
    
    systemctl restart nginx
fi

echo "Creating systemd service file for Gunicorn..."

SERVICE_CONTENT="[Unit]
Description=Gunicorn instance to serve RPi Monitor
After=network.target

[Service]
User=root
Group=root
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/gunicorn --workers 3 --bind unix:/tmp/rpi_monitor.sock -m 007 server:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target"

echo "$SERVICE_CONTENT" > "$SERVICE_FILE_PATH"

echo "Enabling and starting services..."
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl start "$SERVICE_NAME"

echo "-------------------------------------------------"
echo "Installation complete."
echo "The server is now running."
echo "You can check its status with: sudo systemctl status $SERVICE_NAME"
echo "The web interface should be accessible at http://<your-server-ip>:5000"
echo "-------------------------------------------------"

exit 0