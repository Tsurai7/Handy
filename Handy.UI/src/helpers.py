import os
import re
import subprocess
from PIL import Image

import requests
from PIL import ImageTk

from globals import sliders, ICON_FOLDER


def increase_slider(slider_number) -> None:
    current_value = sliders[slider_number].get()
    sliders[slider_number].set(current_value + 5)


def decrease_slider(slider_number) -> None:
    current_value = sliders[slider_number].get()
    sliders[slider_number].set(current_value - 5)


def load_icon(icon_name):
    icon_path = os.path.join(ICON_FOLDER, icon_name)
    try:
        img = Image.open(icon_path).resize((24, 24), Image.Resampling.LANCZOS)
        return ImageTk.PhotoImage(img)
    except Exception as e:
        print(f"Не удалось загрузить иконку {icon_name}: {e}")
        return None


def get_connected_devices():
    devices = []
    result = subprocess.run(['arp', '-a'], stdout=subprocess.PIPE, text=True)

    pattern = r"\((.*?)\) at (.*?) on"
    matches = re.findall(pattern, result.stdout)

    for ip, mac in matches:
        devices.append((ip, mac))
    return devices


def is_esp32(mac_address):
    esp32_prefixes = ['ec:64:c9:ac:f5:cc']

    for prefix in esp32_prefixes:
        if mac_address.upper().startswith(prefix.upper()):
            return True
    return False


def check_esp32_camera(ip):
    url = f"http://{ip}/capture"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return True
    except requests.RequestException:
        pass
    return False


def find_esp32_camera():
    devices = get_connected_devices()
    camera_url = "error"
    for ip, mac in devices:
        if is_esp32(mac):
            print(f"Found ESP32 device with IP: {ip} and MAC: {mac}")

            if check_esp32_camera(ip):
                camera_url = f"http://{ip}/capture"
                print(f"ESP32 Camera found at: {camera_url}")
    return camera_url

