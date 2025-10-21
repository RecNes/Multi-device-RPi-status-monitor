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
echo "Raspberry Pi Web İzleme Uygulaması Kurulumu"
echo "=================================================="

check_and_install() {
    PACKAGE=$1
    echo -n "  -> $PACKAGE kontrol ediliyor... "
    if dpkg -s "$PACKAGE" >/dev/null 2>&1; then
        echo "Kurulu. (✔)"
    else
        echo "Kurulu değil. Kuruluyor..."
        sudo apt install -y "$PACKAGE"
    fi
}

echo "1. Gerekli sistem paketleri kontrol ediliyor ve kuruluyor..."
sudo apt update # Paket listesini güncelle
check_and_install python3
check_and_install python3-pip
check_and_install python3-venv
check_and_install nginx

echo "2. Python Sanal Ortamı ve Bağımlılıklar hazırlanıyor..."

if [ ! -f "requirements.txt" ]; then
    echo "requirements.txt dosyası bulunamadı. Oluşturuluyor..."
    cat > requirements.txt <<EOL
Flask
psutil
gunicorn
EOL
    echo "requirements.txt dosyası oluşturuldu (Gunicorn dahil edildi)."
fi

if [ ! -d "$VENV_DIR" ]; then
    echo "  -> Python Sanal Ortamı ($VENV_DIR) oluşturuluyor..."
    python3 -m venv "$VENV_DIR"
fi
echo "  -> Sanal ortam etkinleştiriliyor ve kütüphaneler yükleniyor..."
source "$VENV_DIR/bin/activate"
pip install --upgrade pip
pip install -r requirements.txt

echo "3. Nginx konfigürasyonu ayarlanıyor..."

if [ ! -f "$NGINX_CONF_SRC" ]; then
    echo "HATA: Nginx konfigürasyon dosyası ($NGINX_CONF_SRC) bulunamadı."
    echo "Lütfen bu betiği çalıştırmadan önce '$NGINX_CONF_SRC' dosyasının proje kök dizininde olduğundan emin olun."
    deactivate
    exit 1
fi

echo "  -> Nginx konfigürasyonu kopyalanıyor..."
sudo cp "$NGINX_CONF_SRC" "$NGINX_CONF_DEST"

if [ ! -L "$NGINX_SYMLINK" ]; then
    echo "  -> Konfigürasyon etkinleştiriliyor (sites-enabled symlink oluşturuluyor)..."
    sudo ln -s "$NGINX_CONF_DEST" "$NGINX_SYMLINK"
else
    echo "  -> Konfigürasyon zaten etkinleştirilmiş."
fi

if [ -f "/etc/nginx/sites-enabled/default" ] || [ -L "/etc/nginx/sites-enabled/default" ]; then
    echo "  -> Varsayılan Nginx sitesi kaldırılıyor..."
    sudo rm -f /etc/nginx/sites-enabled/default
fi

echo "  -> Nginx yapılandırması test ediliyor..."
if ! sudo nginx -t; then
    echo "HATA: Nginx yapılandırma testi başarısız oldu. Lütfen '$NGINX_CONF_SRC' dosyasını kontrol edin."
    deactivate
    exit 1
fi

echo "  -> Nginx yeniden başlatılıyor..."
sudo systemctl restart nginx

echo "4. Gunicorn Systemd Servisi ($SYSTEMD_SERVICE_NAME) kuruluyor..."

echo "  -> Servis dosyası oluşturuluyor..."
sudo bash -c "cat > /etc/systemd/system/$SYSTEMD_SERVICE_NAME" <<EOF
[Unit]
Description=Gunicorn instance for RPi Monitor App
After=network.target

[Service]
User=$CURRENT_USER
Group=www-data

WorkingDirectory=$PROJECT_PATH
ExecStart=$GUNICORN_EXEC --workers 3 --bind unix:/tmp/rpi_monitor.sock
Nice=10
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

echo "  -> Systemd daemon yeniden yükleniyor..."
sudo systemctl daemon-reload

echo "  -> Servis etkinleştiriliyor ve başlatılıyor..."
sudo systemctl enable $SYSTEMD_SERVICE_NAME
sudo systemctl start $SYSTEMD_SERVICE_NAME


echo "=================================================="
echo "Kurulum ve Nginx Ayarları Başarılı!"
echo ""
echo "Servis Durumu Kontrolü:"
echo "--------------------------"
echo "Uygulama artık $SYSTEMD_SERVICE_NAME servisi olarak çalışmaktadır."
echo "Durumunu kontrol etmek için: sudo systemctl status $SYSTEMD_SERVICE_NAME"
echo "Web uygulamanıza Pi'nizin IP adresinden erişebilirsiniz."
echo "Örnek: http://<RPI_IP_ADDRESS>:5000/"
echo ""
echo "=================================================="
