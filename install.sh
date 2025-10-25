#!/usr/bin/env bash

set -e

PROJECT_PATH=$(pwd)
PROJECT_ROOT=$(basename "$PROJECT_PATH")

VENV_DIR="venv"
NGINX_CONF_NAME="rpi_monitor"
NGINX_CONF_SRC="$NGINX_CONF_NAME.nginx" 
NGINX_CONF_DEST="/etc/nginx/sites-available/$NGINX_CONF_NAME"
NGINX_SYMLINK="/etc/nginx/sites-enabled/$NGINX_CONF_NAME"

SYSTEMD_SERVICE_NAME="rpi_monitor.service"
CURRENT_USER=$(whoami)
GUNICORN_EXEC="$PROJECT_PATH/$VENV_DIR/bin/gunicorn"

echo "=================================================="
echo "Raspberry Pi Web Monitoring App Setup"
echo "=================================================="

check_and_install() {
    PACKAGE=$1
    echo -n "  -> Checking $PACKAGE... "
    if dpkg -s "$PACKAGE" >/dev/null 2>&1; then
        echo "Installed. (✔)"
    else
        echo "Not installed. Installing..."
        sudo apt install -y "$PACKAGE"
    fi
}

echo "1. Checking and installing required system packages..."
sudo apt update # Update package list
check_and_install python3
check_and_install python3-pip
check_and_install python3-venv
check_and_install nginx

echo "2. Preparing Python Virtual Environment and Dependencies..."

if [ ! -f "requirements.txt" ]; then
    echo "requirements.txt not found. Creating..."
    cat > requirements.txt <<EOL
Flask
psutil
gunicorn
EOL
    echo "requirements.txt created (Gunicorn included)."
fi

if [ ! -d "$VENV_DIR" ]; then
    echo "  -> Creating Python Virtual Environment ($VENV_DIR)..."
    python3 -m venv "$VENV_DIR"
fi
echo "  -> Activating virtual environment and installing libraries..."
source "$VENV_DIR/bin/activate"
pip install --upgrade pip
pip install -r requirements.txt

echo "3. Setting up Nginx configuration..."

if [ ! -f "$NGINX_CONF_SRC" ]; then
    echo "ERROR: Nginx configuration file ($NGINX_CONF_SRC) not found."
    echo "Please make sure the '$NGINX_CONF_SRC' file is in the project root directory before running this script."
    deactivate
    exit 1
fi

echo "  -> Copying Nginx configuration..."
sudo cp "$NGINX_CONF_SRC" "$NGINX_CONF_DEST"

if [ ! -L "$NGINX_SYMLINK" ]; then
    echo "  -> Enabling configuration (creating sites-enabled symlink)..."
    sudo ln -s "$NGINX_CONF_DEST" "$NGINX_SYMLINK"
else
    echo "  -> Configuration already enabled."
fi

if [ -f "/etc/nginx/sites-enabled/default" ] || [ -L "/etc/nginx/sites-enabled/default" ]; then
    echo "  -> Removing default Nginx site..."
    sudo rm -f /etc/nginx/sites-enabled/default
fi

echo "  -> Testing Nginx configuration..."
if ! sudo nginx -t; then
    echo "ERROR: Nginx configuration test failed. Please check the '$NGINX_CONF_SRC' file."
    deactivate
    exit 1
fi

echo "  -> Restarting Nginx..."
sudo systemctl restart nginx

echo "4. Installing Gunicorn Systemd Service ($SYSTEMD_SERVICE_NAME)..."

echo "  -> Creating service file..."
sudo bash -c "cat > /etc/systemd/system/$SYSTEMD_SERVICE_NAME" <<EOF
[Unit]
Description=Gunicorn instance for RPi Monitor App
After=network.target

[Service]
User=$CURRENT_USER
Group=www-data

WorkingDirectory=$PROJECT_PATH
ExecStart=$GUNICORN_EXEC --workers 3 --bind unix:/tmp/rpi_monitor.sock app:app
Nice=10
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

echo "  -> Reloading Systemd daemon..."
sudo systemctl daemon-reload

echo "  -> Enabling and starting service..."
sudo systemctl enable $SYSTEMD_SERVICE_NAME
sudo systemctl start $SYSTEMD_SERVICE_NAME


echo "=================================================="
echo "Installation and Nginx Setup Successful!"
echo ""
echo "Service Status Check:"
echo "--------------------------"
echo "The application is now running as the $SYSTEMD_SERVICE_NAME service."
echo "To check its status: sudo systemctl status $SYSTEMD_SERVICE_NAME"
echo "You can access your web application from your Pi's IP address."
echo "Example: http://<RPI_IP_ADDRESS>:5000/"
echo ""
echo "=================================================="
