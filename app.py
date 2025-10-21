import subprocess
import re
import time

from copy import deepcopy

import psutil
from flask import Flask, render_template


app = Flask(__name__)


def measure_vcgen_volt(target):
    """vcgencmd measure_volts <target> komutunu çalıştırır ve voltajı çeker."""
    try:
        volt_output = subprocess.check_output(f"vcgencmd measure_volts {target}", shell=True).decode()
        match = re.search(r'volt=(\d+\.?\d*)V', volt_output)
        return f"{match.group(1)} V" if match else f"N/A ({target} Okunamadı)"
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "N/A (vcgencmd Hatası)"


def get_throttled_status():
    status_list = []
    status_code = ""

    THROTTLED_BITS = {
        0: "Şu anda düşük voltaj var (⚡️)",
        1: "ARM frekansı şu anda kısıtlanmış",
        2: "Şu anda kısıtlama (throttling) var",
        3: "Yazılım sıcaklık sınırına ulaşıldı (🌡️)",
        16: "Yeniden başlatmadan beri düşük voltaj oluştu (⚠️)",
        17: "Yeniden başlatmadan beri ARM frekansı kısıtlandı",
        18: "Yeniden başlatmadan beri kısıtlama (throttling) oluştu",
        19: "Yeniden başlatmadan beri yazılım sıcaklık sınırına ulaşıldı",
    }

    try:
        output = subprocess.check_output("vcgencmd get_throttled", shell=True).decode()
        status_code_match = re.search(r'throttled=(0x[0-9a-fA-F]+)', output)

        if status_code_match:
            status_code_hex = status_code_match.group(1)
            status_code = deepcopy(status_code_hex)
            status_int = int(status_code_hex, 16)

            for bit, message in THROTTLED_BITS.items():
                if (status_int >> bit) & 1:
                    status_list.append(message)

            if not status_list and status_int == 0:
                status_list.append("Her şey yolunda, kısıtlama yok. (✅)")

        else:
            status_list.append("vcgencmd çıktısı çözülemedi.")
            status_code = "N/A"
             
    except (subprocess.CalledProcessError, FileNotFoundError):
        status_list.append("vcgencmd komutu bulunamadı veya çalıştırılamadı.")
        status_code = "Hata"

    return status_code, status_list


def get_pi_specific_info():
    info = {}

    try:
        temp_output = subprocess.check_output("vcgencmd measure_temp", shell=True).decode()
        match = re.search(r'temp=(\d+\.?\d*)\'C', temp_output)
        info['cpu_temp'] = f"{match.group(1)} °C" if match else "N/A"
    except (subprocess.CalledProcessError, FileNotFoundError):
        info['cpu_temp'] = "N/A (vcgencmd Hatası)"

    info['cpu_voltage'] = measure_vcgen_volt("core")
    info['sdram_c_voltage'] = measure_vcgen_volt("sdram_c")
    info['sdram_i_voltage'] = measure_vcgen_volt("sdram_i")
    info['sdram_p_voltage'] = measure_vcgen_volt("sdram_p")

    try:
        freq_output = subprocess.check_output("vcgencmd measure_clock arm", shell=True).decode()
        match = re.search(r'freq\((\d+)\)=(\d+)', freq_output)
        if match:
            frequency_mhz = int(match.group(2)) / 1000000
            info['cpu_frequency'] = f"{frequency_mhz:.0f} MHz"
        else:
            info['cpu_frequency'] = "N/A (Frekans Okunamadı)"
    except (subprocess.CalledProcessError, FileNotFoundError):
        info['cpu_frequency'] = "N/A (vcgencmd Hatası)"

    info['throttled_code'], info['throttled_status'] = get_throttled_status()
        
    return info


def get_system_info():
    cpu_usage = psutil.cpu_percent(interval=None)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage('/')

    general_info = {
        "cpu_usage": f"{cpu_usage:.1f}%",
        "ram_usage": f"{ram.percent:.1f}%",
        "disk_usage": f"{disk.percent:.1f}%",
        "uptime": get_uptime(),
        "boot_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(psutil.boot_time()))
    }

    pi_info = get_pi_specific_info()
    current_time = time.time()

    return {**general_info, **pi_info, "current_time": current_time}


def get_uptime():
    uptime_seconds = time.time() - psutil.boot_time()
    minutes, seconds = divmod(uptime_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)

    parts = []
    if days > 0: parts.append(f"{int(days)} gün")
    if hours > 0: parts.append(f"{int(hours)} saat")
    if minutes > 0: parts.append(f"{int(minutes)} dakika")

    return ", ".join(parts) if parts else "Birkaç saniye"


@app.route('/')
def index():
    data = get_system_info()
    return render_template('index.html', data=data)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
