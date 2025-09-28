import os
import sqlite3
import requests
from pathlib import Path
import hashlib
import json
import math
import time


class TileManager:
    def __init__(self, data_dir):
        self.data_dir = Path(data_dir)
        self.tiles_dir = self.data_dir / "tiles"
        self.tiles_db = self.data_dir / "tiles.db"
        self.tiles_dir.mkdir(parents=True, exist_ok=True)

        self.init_database()
        self.load_offline_tilesets()

    def init_database(self):
        """Инициализирует базу данных для хранения информации о тайлах"""
        conn = sqlite3.connect(self.tiles_db)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tiles (
                url TEXT PRIMARY KEY,
                filename TEXT,
                added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tilesets (
                name TEXT PRIMARY KEY,
                bounds TEXT,
                min_zoom INTEGER,
                max_zoom INTEGER,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.commit()
        conn.close()

    def load_offline_tilesets(self):
        """Загружает информацию о доступных офлайн тайлсетах"""
        self.offline_tilesets = {}
        conn = sqlite3.connect(self.tiles_db)
        cursor = conn.cursor()

        cursor.execute("SELECT name, bounds, min_zoom, max_zoom FROM tilesets")
        for row in cursor.fetchall():
            name, bounds, min_zoom, max_zoom = row
            self.offline_tilesets[name] = {
                'bounds': json.loads(bounds),
                'min_zoom': min_zoom,
                'max_zoom': max_zoom
            }

        conn.close()

    def download_tile(self, url):
        """Скачивает и сохраняет тайл"""
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                # Создаем хеш имени файла из URL
                filename = hashlib.md5(url.encode()).hexdigest() + ".png"
                filepath = self.tiles_dir / filename

                # Сохраняем файл
                with open(filepath, 'wb') as f:
                    f.write(response.content)

                # Сохраняем в базу данных
                conn = sqlite3.connect(self.tiles_db)
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT OR REPLACE INTO tiles (url, filename) VALUES (?, ?)",
                    (url, filename)
                )
                conn.commit()
                conn.close()

                return True
        except Exception as e:
            print(f"Ошибка загрузки тайла {url}: {e}")

        return False

    def get_tile(self, url):
        """Получает тайл из кэша или возвращает None"""
        conn = sqlite3.connect(self.tiles_db)
        cursor = conn.cursor()

        cursor.execute("SELECT filename FROM tiles WHERE url = ?", (url,))
        result = cursor.fetchone()
        conn.close()

        if result:
            filename = result[0]
            filepath = self.tiles_dir / filename
            if filepath.exists():
                with open(filepath, 'rb') as f:
                    return f.read()

        return None

    def get_tile_data_url(self, url):
        """Возвращает Data URL для тайла"""
        tile_data = self.get_tile(url)
        if tile_data:
            import base64
            base64_data = base64.b64encode(tile_data).decode('utf-8')
            return f"data:image/png;base64,{base64_data}"
        return None

    def is_tile_cached(self, url):
        """Проверяет, есть ли тайл в кэше"""
        return self.get_tile(url) is not None

    def download_area(self, bounds, zoom_levels, name, progress_callback=None, thread=None):
        """Скачивает тайлы для указанной области и уровней масштабирования"""
        min_lat, min_lon, max_lat, max_lon = bounds
        tiles_downloaded = 0
        total_tiles = 0

        # Подсчитываем общее количество тайлов
        for zoom in zoom_levels:
            min_tile_x = self.lon_to_tile_x(min_lon, zoom)
            max_tile_x = self.lon_to_tile_x(max_lon, zoom)
            min_tile_y = self.lat_to_tile_y(max_lat, zoom)
            max_tile_y = self.lat_to_tile_y(min_lat, zoom)

            total_tiles += (max_tile_x - min_tile_x + 1) * (max_tile_y - min_tile_y + 1)

        print(f"Всего тайлов для загрузки: {total_tiles}")

        current_tile = 0
        for zoom in zoom_levels:
            # Преобразуем координаты в тайлы
            min_tile_x = self.lon_to_tile_x(min_lon, zoom)
            max_tile_x = self.lon_to_tile_x(max_lon, zoom)
            min_tile_y = self.lat_to_tile_y(max_lat, zoom)
            max_tile_y = self.lat_to_tile_y(min_lat, zoom)

            print(f"Загрузка zoom {zoom}: x({min_tile_x}-{max_tile_x}), y({min_tile_y}-{max_tile_y})")

            for x in range(min_tile_x, max_tile_x + 1):
                for y in range(min_tile_y, max_tile_y + 1):
                    # Проверяем, не была ли отмена
                    if thread and not thread._is_running:
                        print("Загрузка прервана пользователем")
                        return tiles_downloaded

                    current_tile += 1

                    # Используем CartoDB Voyager (цветной стиль с русскими подписями)
                    url = f"https://cartodb-basemaps-a.global.ssl.fastly.net/rastertiles/voyager/{zoom}/{x}/{y}.png"

                    if not self.is_tile_cached(url):
                        if self.download_tile(url):
                            tiles_downloaded += 1
                            if tiles_downloaded % 10 == 0:
                                print(f"Загружено {tiles_downloaded}/{total_tiles} тайлов...")

                    # Отправляем прогресс
                    if progress_callback:
                        progress_callback.emit(current_tile, total_tiles)

                    # Небольшая задержка чтобы не перегружать сервер
                    time.sleep(0.01)

        # Сохраняем информацию о тайлсете
        if tiles_downloaded > 0:
            conn = sqlite3.connect(self.tiles_db)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO tilesets (name, bounds, min_zoom, max_zoom) VALUES (?, ?, ?, ?)",
                (name, json.dumps(bounds), min(zoom_levels), max(zoom_levels))
            )
            conn.commit()
            conn.close()

            self.load_offline_tilesets()

        return tiles_downloaded

    def estimate_download_size(self, bounds, zoom_levels):
        """Оценивает размер загрузки в МБ"""
        total_tiles = 0
        for zoom in zoom_levels:
            min_tile_x = self.lon_to_tile_x(bounds[1], zoom)
            max_tile_x = self.lon_to_tile_x(bounds[3], zoom)
            min_tile_y = self.lat_to_tile_y(bounds[2], zoom)
            max_tile_y = self.lat_to_tile_y(bounds[0], zoom)

            total_tiles += (max_tile_x - min_tile_x + 1) * (max_tile_y - min_tile_y + 1)

        # Средний размер тайла ~15KB
        estimated_size_mb = (total_tiles * 15) / 1024
        return round(estimated_size_mb, 1)

    @staticmethod
    def lon_to_tile_x(lon, zoom):
        return int((lon + 180.0) / 360.0 * (2 ** zoom))

    @staticmethod
    def lat_to_tile_y(lat, zoom):
        lat_rad = math.radians(lat)
        return int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * (2 ** zoom))

    def get_stats(self):
        """Возвращает статистику по кэшированным тайлам"""
        conn = sqlite3.connect(self.tiles_db)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM tiles")
        total_tiles = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM tilesets")
        total_tilesets = cursor.fetchone()[0]

        # Получаем размер базы тайлов
        total_size = 0
        for file_path in self.tiles_dir.glob("*.png"):
            total_size += file_path.stat().st_size

        conn.close()

        return {
            'total_tiles': total_tiles,
            'total_tilesets': total_tilesets,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'tilesets': self.offline_tilesets
        }

    def clear_cache(self):
        """Очищает кэш тайлов"""
        conn = sqlite3.connect(self.tiles_db)
        cursor = conn.cursor()

        # Удаляем записи из базы данных
        cursor.execute("DELETE FROM tiles")
        cursor.execute("DELETE FROM tilesets")
        conn.commit()
        conn.close()

        # Удаляем файлы тайлов
        for file_path in self.tiles_dir.glob("*.png"):
            try:
                file_path.unlink()
            except Exception as e:
                print(f"Ошибка удаления файла {file_path}: {e}")

        self.offline_tilesets = {}
        return True