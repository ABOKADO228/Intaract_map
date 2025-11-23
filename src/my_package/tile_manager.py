import os
import sqlite3
import requests
from pathlib import Path
import hashlib
import json
import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading


class TileManager:
    def __init__(self, data_dir):
        self.data_dir = Path(data_dir)
        self.tiles_dir = self.data_dir / "tiles"
        self.tiles_db = self.data_dir / "tiles.db"
        self.tiles_dir.mkdir(parents=True, exist_ok=True)

        # CartoDB Voyager конфигурация
        self.tile_source = {
            'url_template': 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png',
            'subdomains': ['a', 'b', 'c', 'd'],
            'attribution': '© OpenStreetMap © CARTO'
        }

        # Кэш для быстрого доступа
        self._tile_cache = {}
        self._cache_lock = threading.Lock()
        self._popular_tiles = set()
        self._max_memory_cache = 1000

        self.init_database()
        self.load_offline_tilesets()
        self.preload_popular_tiles()

    def init_database(self):
        """Инициализирует базу данных для хранения информации о тайлах"""
        conn = sqlite3.connect(self.tiles_db)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tiles (
                url TEXT PRIMARY KEY,
                filename TEXT,
                added_date TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tilesets (
                name TEXT PRIMARY KEY,
                bounds TEXT,
                min_zoom INTEGER,
                max_zoom INTEGER,
                created_date TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tileset_tiles (
                tileset TEXT,
                url TEXT,
                PRIMARY KEY (tileset, url)
            )
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_tileset_tiles_url
            ON tileset_tiles(url)
        ''')

        # Проверяем и добавляем отсутствующие столбцы
        cursor.execute("PRAGMA table_info(tiles)")
        columns = [column[1] for column in cursor.fetchall()]

        if 'access_count' not in columns:
            try:
                cursor.execute('ALTER TABLE tiles ADD COLUMN access_count INTEGER DEFAULT 0')
                print("Добавлен столбец access_count в таблицу tiles")
            except sqlite3.OperationalError as e:
                print(f"Ошибка добавления столбца access_count: {e}")

        if 'last_access' not in columns:
            try:
                cursor.execute('ALTER TABLE tiles ADD COLUMN last_access TEXT')
                print("Добавлен столбец last_access в таблицу tiles")
            except sqlite3.OperationalError as e:
                print(f"Ошибка добавления столбца last_access: {e}")

        try:
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_tiles_access_count 
                ON tiles(access_count DESC)
            ''')
        except sqlite3.OperationalError as e:
            print(f"Ошибка создания индекса: {e}")

        conn.commit()
        conn.close()

    def load_offline_tilesets(self):
        """Загружает информацию о доступных офлайн тайлсетах"""
        self.offline_tilesets = {}
        conn = sqlite3.connect(self.tiles_db)
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT name, bounds, min_zoom, max_zoom FROM tilesets")
            for row in cursor.fetchall():
                name, bounds, min_zoom, max_zoom = row
                self.offline_tilesets[name] = {
                    'bounds': json.loads(bounds),
                    'min_zoom': min_zoom,
                    'max_zoom': max_zoom
                }
        except sqlite3.OperationalError as e:
            print(f"Ошибка загрузки tilesets: {e}")
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tilesets (
                    name TEXT PRIMARY KEY,
                    bounds TEXT,
                    min_zoom INTEGER,
                    max_zoom INTEGER,
                    created_date TEXT
                )
            ''')
            conn.commit()

        conn.close()

    def preload_popular_tiles(self):
        """Предзагружает популярные тайлы в память"""
        try:
            conn = sqlite3.connect(self.tiles_db)
            cursor = conn.cursor()

            cursor.execute("PRAGMA table_info(tiles)")
            columns = [column[1] for column in cursor.fetchall()]

            if 'access_count' in columns:
                cursor.execute('''
                    SELECT url, filename FROM tiles 
                    WHERE access_count > 0 
                    ORDER BY access_count DESC 
                    LIMIT ?
                ''', (self._max_memory_cache // 2,))

                for url, filename in cursor.fetchall():
                    filepath = self.tiles_dir / filename
                    if filepath.exists():
                        try:
                            with open(filepath, 'rb') as f:
                                with self._cache_lock:
                                    self._tile_cache[url] = f.read()
                                    self._popular_tiles.add(url)
                        except Exception as e:
                            print(f"Ошибка предзагрузки тайла {filename}: {e}")

            conn.close()
            print(f"Предзагружено {len(self._tile_cache)} популярных тайлов в память")
        except Exception as e:
            print(f"Ошибка предзагрузки тайлов: {e}")

    def get_current_timestamp(self):
        """Возвращает текущую временную метку в строковом формате"""
        return time.strftime('%Y-%m-%d %H:%M:%S')

    def update_access_count(self, url):
        """Обновляет счетчик обращений к тайлу"""
        try:
            conn = sqlite3.connect(self.tiles_db)
            cursor = conn.cursor()

            cursor.execute("PRAGMA table_info(tiles)")
            columns = [column[1] for column in cursor.fetchall()]

            if 'access_count' in columns and 'last_access' in columns:
                cursor.execute('''
                    UPDATE tiles 
                    SET access_count = access_count + 1, last_access = ?
                    WHERE url = ?
                ''', (self.get_current_timestamp(), url))
            else:
                print("Столбцы access_count или last_access не существуют")

            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Ошибка обновления счетчика доступа: {e}")

    def get_tile_url(self, zoom, x, y):
        """Генерирует URL для тайла CartoDB Voyager"""
        subdomain = self.tile_source['subdomains'][(x + y) % len(self.tile_source['subdomains'])]
        url = self.tile_source['url_template'].format(
            s=subdomain,
            z=zoom,
            x=x,
            y=y,
            r=''
        )
        return url

    def download_tile(self, url):
        """Скачивает и сохраняет тайл"""
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                filename = hashlib.md5(url.encode()).hexdigest() + ".png"
                filepath = self.tiles_dir / filename

                with open(filepath, 'wb') as f:
                    f.write(response.content)

                conn = sqlite3.connect(self.tiles_db)
                cursor = conn.cursor()

                cursor.execute("PRAGMA table_info(tiles)")
                columns = [column[1] for column in cursor.fetchall()]

                if 'access_count' in columns and 'last_access' in columns:
                    cursor.execute(
                        "INSERT OR REPLACE INTO tiles (url, filename, added_date, access_count, last_access) VALUES (?, ?, ?, 0, ?)",
                        (url, filename, self.get_current_timestamp(), self.get_current_timestamp())
                    )
                else:
                    cursor.execute(
                        "INSERT OR REPLACE INTO tiles (url, filename, added_date) VALUES (?, ?, ?)",
                        (url, filename, self.get_current_timestamp())
                    )

                conn.commit()
                conn.close()

                return True
        except Exception as e:
            print(f"Ошибка загрузки тайла {url}: {e}")

        return False

    def download_tile_batch(self, urls):
        """Скачивает несколько тайлов параллельно"""

        def download_single(url):
            try:
                if not self.is_tile_cached(url):
                    return self.download_tile(url), url
                return True, url
            except Exception as e:
                print(f"Ошибка при пакетной загрузке {url}: {e}")
                return False, url

        successful = 0
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_url = {executor.submit(download_single, url): url for url in urls}
            for future in as_completed(future_to_url):
                result, url = future.result()
                if result:
                    successful += 1

        return successful

    def get_tile(self, url):
        """Получает тайл из кэша или возвращает None"""
        with self._cache_lock:
            if url in self._tile_cache:
                return self._tile_cache[url]

        conn = sqlite3.connect(self.tiles_db)
        cursor = conn.cursor()

        cursor.execute("SELECT filename FROM tiles WHERE url = ?", (url,))
        result = cursor.fetchone()

        if result:
            filename = result[0]
            filepath = self.tiles_dir / filename
            if filepath.exists():
                try:
                    with open(filepath, 'rb') as f:
                        tile_data = f.read()

                        self.update_access_count(url)

                        with self._cache_lock:
                            if len(self._tile_cache) < self._max_memory_cache:
                                self._tile_cache[url] = tile_data

                        conn.close()
                        return tile_data
                except Exception as e:
                    print(f"Ошибка чтения файла тайла {filepath}: {e}")

        conn.close()
        return None

    def get_tile_data_url(self, url):
        """Возвращает Data URL для тайла"""
        try:
            tile_data = self.get_tile(url)
            if tile_data:
                import base64
                base64_data = base64.b64encode(tile_data).decode('utf-8')
                return f"data:image/png;base64,{base64_data}"
        except Exception as e:
            print(f"Ошибка создания Data URL для {url}: {e}")

        return ""

    def is_tile_cached(self, url):
        """Проверяет, есть ли тайл в кэше"""
        with self._cache_lock:
            if url in self._tile_cache:
                return True

        conn = sqlite3.connect(self.tiles_db)
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM tiles WHERE url = ?", (url,))
        result = cursor.fetchone() is not None
        conn.close()
        return result

    def download_area(self, bounds, zoom_levels, name, progress_callback=None, thread=None):
        """Скачивает тайлы CartoDB Voyager для указанной области"""
        min_lat, min_lon, max_lat, max_lon = bounds
        tiles_downloaded = 0

        all_urls = []
        for zoom in zoom_levels:
            min_tile_x = self.lon_to_tile_x(min_lon, zoom)
            max_tile_x = self.lon_to_tile_x(max_lon, zoom)
            min_tile_y = self.lat_to_tile_y(max_lat, zoom)
            max_tile_y = self.lat_to_tile_y(min_lat, zoom)

            print(f"Zoom {zoom}: tiles from ({min_tile_x}, {min_tile_y}) to ({max_tile_x}, {max_tile_y})")

            for x in range(min_tile_x, max_tile_x + 1):
                for y in range(min_tile_y, max_tile_y + 1):
                    url = self.get_tile_url(zoom, x, y)
                    all_urls.append(url)

        total_tiles = len(all_urls)
        print(f"Всего тайлов CartoDB Voyager для загрузки: {total_tiles}")

        batch_size = 50
        for i in range(0, len(all_urls), batch_size):
            if thread and not thread._is_running:
                print("Загрузка прервана пользователем")
                return tiles_downloaded

            batch_urls = all_urls[i:i + batch_size]
            downloaded_in_batch = self.download_tile_batch(batch_urls)
            tiles_downloaded += downloaded_in_batch

            if progress_callback:
                progress_callback.emit(i + len(batch_urls), total_tiles)

            time.sleep(0.1)

        if tiles_downloaded > 0:
            conn = sqlite3.connect(self.tiles_db)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO tilesets (name, bounds, min_zoom, max_zoom, created_date) VALUES (?, ?, ?, ?, ?)",
                (name, json.dumps(bounds), min(zoom_levels), max(zoom_levels), self.get_current_timestamp())
            )

            try:
                cursor.executemany(
                    "INSERT OR IGNORE INTO tileset_tiles (tileset, url) VALUES (?, ?)",
                    [(name, url) for url in all_urls],
                )
            except sqlite3.OperationalError as e:
                print(f"Ошибка сохранения связей тайлов с областью {name}: {e}")

            conn.commit()
            conn.close()

            self.load_offline_tilesets()

        return tiles_downloaded

    def download_visible_area(self, bounds, zoom_levels, name, progress_callback=None, thread=None):
        """Скачивает тайлы только для видимой области на выбранных zoom уровнях"""
        return self.download_area(bounds, zoom_levels, name, progress_callback, thread)

    def estimate_download_size(self, bounds, zoom_levels):
        """Оценивает размер загрузки в МБ для CartoDB Voyager"""
        total_tiles = 0
        for zoom in zoom_levels:
            min_tile_x = self.lon_to_tile_x(bounds[1], zoom)
            max_tile_x = self.lon_to_tile_x(bounds[3], zoom)
            min_tile_y = self.lat_to_tile_y(bounds[2], zoom)
            max_tile_y = self.lat_to_tile_y(bounds[0], zoom)

            total_tiles += (max_tile_x - min_tile_x + 1) * (max_tile_y - min_tile_y + 1)

        estimated_size_mb = (total_tiles * 20) / 1024
        return round(estimated_size_mb, 1)

    def estimate_visible_area_size(self, bounds, zoom):
        """Оценивает размер загрузки для видимой области (для обратной совместимости)"""
        return self.estimate_download_size(bounds, [zoom])

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

        total_size = 0
        for file_path in self.tiles_dir.glob("*.png"):
            total_size += file_path.stat().st_size

        cursor.execute("PRAGMA table_info(tiles)")
        columns = [column[1] for column in cursor.fetchall()]

        popular_tiles = []
        if 'access_count' in columns:
            cursor.execute('''
                SELECT url, access_count FROM tiles 
                WHERE access_count > 0 
                ORDER BY access_count DESC 
                LIMIT 10
            ''')
            popular_tiles = cursor.fetchall()

        conn.close()

        return {
            'total_tiles': total_tiles,
            'total_tilesets': total_tilesets,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'memory_cached': len(self._tile_cache),
            'popular_tiles': popular_tiles,
            'tilesets': self.offline_tilesets
        }

    def delete_tileset(self, name):
        """Удаляет конкретную офлайн-область, не затрагивая остальные."""
        try:
            conn = sqlite3.connect(self.tiles_db)
            cursor = conn.cursor()

            try:
                cursor.execute("SELECT url FROM tileset_tiles WHERE tileset = ?", (name,))
            except sqlite3.OperationalError:
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS tileset_tiles (
                        tileset TEXT,
                        url TEXT,
                        PRIMARY KEY (tileset, url)
                    )
                ''')
                cursor.execute("SELECT url FROM tileset_tiles WHERE tileset = ?", (name,))

            urls = [row[0] for row in cursor.fetchall()]

            if not urls:
                cursor.execute("DELETE FROM tilesets WHERE name = ?", (name,))
                cursor.execute("DELETE FROM tileset_tiles WHERE tileset = ?", (name,))
                conn.commit()
                conn.close()
                self.load_offline_tilesets()
                return True

            for url in urls:
                with self._cache_lock:
                    self._tile_cache.pop(url, None)

                cursor.execute(
                    "SELECT COUNT(*) FROM tileset_tiles WHERE url = ? AND tileset != ?",
                    (url, name),
                )
                other_references = cursor.fetchone()[0]

                if other_references == 0:
                    cursor.execute("SELECT filename FROM tiles WHERE url = ?", (url,))
                    row = cursor.fetchone()
                    if row:
                        filename = row[0]
                        file_path = self.tiles_dir / filename
                        if file_path.exists():
                            try:
                                file_path.unlink()
                            except Exception as e:
                                print(f"Ошибка удаления файла {file_path}: {e}")

                    cursor.execute("DELETE FROM tiles WHERE url = ?", (url,))

            cursor.execute("DELETE FROM tileset_tiles WHERE tileset = ?", (name,))
            cursor.execute("DELETE FROM tilesets WHERE name = ?", (name,))
            conn.commit()
            conn.close()

            self.load_offline_tilesets()
            return True
        except Exception as e:
            print(f"Ошибка удаления области {name}: {e}")
            return False

    def clear_cache(self):
        """Очищает кэш тайлов"""
        with self._cache_lock:
            self._tile_cache.clear()
            self._popular_tiles.clear()

        conn = sqlite3.connect(self.tiles_db)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM tiles")
        cursor.execute("DELETE FROM tilesets")
        cursor.execute("DELETE FROM tileset_tiles")
        conn.commit()
        conn.close()

        for file_path in self.tiles_dir.glob("*.png"):
            try:
                file_path.unlink()
            except Exception as e:
                print(f"Ошибка удаления файла {file_path}: {e}")

        self.offline_tilesets = {}
        return True