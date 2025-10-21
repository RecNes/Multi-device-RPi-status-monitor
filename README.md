# 🍓 Raspberry Pi Durum İzleme Sayfası

Bu proje, Raspberry Pi cihazınızın temel sistem metriklerini (CPU kullanımı, RAM, disk, sıcaklık, voltaj ve kısıtlama durumu) gerçek zamanlı olarak gösteren hafif bir Flask tabanlı web uygulamasıdır. Uygulama, Nginx ve Gunicorn arkasında, sistem servisi olarak çalışacak şekilde tasarlanmıştır.

## Özellikler

* **Gerçek Zamanlı Veriler:** CPU, RAM ve Disk kullanım yüzdeleri.

* **Raspberry Pi'ye Özgü Metrikler:**

  * İşlemci Sıcaklığı (`vcgencmd measure_temp`).

  * Çekirdek (Core) ve SDRAM Voltajları.

  * **Kritik Durum Kontrolü:** Düşük voltaj veya aşırı ısınma nedeniyle oluşan kısıtlama (throttling) durumunun kontrolü ve uyarısı (`vcgencmd get_throttled`).

* **Mimari:** Flask + Gunicorn + Nginx (Proxy Pass) + systemd.

* **Kolay Kurulum:** Tek bir Bash betiği (`setup.sh`) ile tüm bağımlılıkları ve servisleri otomatik olarak kurar.

## Kurulum (Raspberry Pi OS)

Projenizi Git ile indirdikten sonra, kurulumu tek bir komutla tamamlayabilirsiniz.

### 1. Projeyi İndirme


# Proje dizininizi oluşturun ve içine girin

git clone https://github.com/RecNes/stand-alone-RPi-status-monitoring-page.git
cd stand-alone-RPi-status-monitoring-page/


### 2. Kurulum Betiğini Çalıştırma

`setup.sh` betiği, tüm sistem bağımlılıklarını (Nginx), Python bağımlılıklarını (`Flask`, `psutil`, `gunicorn`) kuracak ve uygulamayı bir `systemd` servisi olarak ayarlayıp Nginx ile bağlayacaktır.

**Not:** Betik çalışırken root yetkisi gerektiren komutlar (`sudo`) kullanacaktır.


chmod +x setup.sh
./setup.sh


### Betik Ne Yapar?

1. **Sistem Kontrolü:** `python3`, `python3-venv` ve `nginx` paketlerinin kurulu olup olmadığını kontrol eder ve eksikleri kurar.

2. **Sanal Ortam:** Proje klasörünüzün içine `venv` adında bir sanal ortam oluşturur.

3. **Bağımlılıklar:** `requirements.txt` dosyasındaki kütüphaneleri (Flask, psutil, gunicorn) bu ortama yükler.

4. **Nginx Konfigürasyonu:** Proje kök dizinindeki `rpi_monitor.nginx` dosyasını `/etc/nginx/sites-available/` dizinine kopyalar ve etkinleştirir.

5. **Systemd Servisi:** Uygulamayı Gunicorn ile başlatmak için `/etc/systemd/system/rpi_monitor.service` dosyasını oluşturur, servisi etkinleştirir ve hemen başlatır.

## Kullanım

Kurulum tamamlandıktan sonra uygulamaya erişmek için, Raspberry Pi'nizin IP adresini web tarayıcınıza yazmanız yeterlidir.

**Örnek:** `http://[Raspberry Pi'nizin IP Adresi]:5000/`

## Bakım ve Yönetim

Uygulamanız bir `systemd` servisi olarak çalıştığı için, yönetim işlemleri basittir:

| İşlem | Komut | Açıklama |
| :--- | :--- | :--- |
| **Durumu Kontrol Etme** | `sudo systemctl status rpi_monitor.service` | Servisin çalışıp çalışmadığını, son günlükleri ve hataları gösterir. |
| **Yeniden Başlatma** | `sudo systemctl restart rpi_monitor.service` | Kodda bir değişiklik yaptığınızda servisi yeniden başlatır. |
| **Durdurma** | `sudo systemctl stop rpi_monitor.service` | Servisi durdurur. |
| **Otomatik Başlatmayı Kaldırma** | `sudo systemctl disable rpi_monitor.service` | Cihaz yeniden başlatıldığında otomatik olarak çalışmasını engeller. |

## Proje Dosyaları

| Dosya Adı | Açıklama |
| :--- | :--- |
| `app.py` | Flask uygulamasının ana Python kodu. Sistem metriklerini toplar. |
| `templates/index.html` | Uygulamanın arayüz şablonu. Verileri düzenli bir şekilde gösterir. |
| `requirements.txt` | Python bağımlılıklarını listeler (`Flask`, `psutil`, `gunicorn`). |
| `setup.sh` | Tüm sistem kurulumunu otomatikleştiren Bash betiği. |
| `rpi_monitor.nginx` | Nginx için proxy konfigürasyonu. İsteği Gunicorn soketine yönlendirir. |
