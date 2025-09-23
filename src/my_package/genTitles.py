import os
import requests
from concurrent.futures import ThreadPoolExecutor


def download_tile(z, x, y):
    """Скачивает один тайл"""
    url = f"https://tile.openstreetmap.org/{z}/{x}/{y}.png"
    folder = f"offline-tiles/{z}/{x}"
    os.makedirs(folder, exist_ok=True)
    filepath = f"{folder}/{y}.png"

    if not os.path.exists(filepath):
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                with open(filepath, 'wb') as f:
                    f.write(response.content)
                print(f"Скачан: {z}/{x}/{y}")
            else:
                print(f"Ошибка {response.status_code}: {z}/{x}/{y}")
        except Exception as e:
            print(f"Ошибка скачивания {z}/{x}/{y}: {e}")


def download_area():
    """Скачивает тайлы для области вокруг Санкт-Петербурга"""
    # Координаты центра: 59.93, 30.34
    # Zoom levels: 10-15

    # Для zoom 12 (пример)
    z = 12
    x_center = 2206  # Примерные координаты для Санкт-Петербурга
    y_center = 1274

    # Скачиваем область 3x3 тайла вокруг центра
    tiles = []
    for x in range(x_center - 1, x_center + 2):
        for y in range(y_center - 1, y_center + 2):
            tiles.append((z, x, y))

    # Используем многопоточность для ускорения
    with ThreadPoolExecutor(max_workers=5) as executor:
        executor.map(lambda args: download_tile(*args), tiles)


if __name__ == "__main__":
    download_area()