import sys
import os
import logging


def set_qt_plugin_path():
    if getattr(sys, 'frozen', False):
        # Если приложение собрано в exe
        base_path = sys._MEIPASS
        # Устанавливаем путь к плагинам Qt
        qt_plugin_path = os.path.join(base_path, 'qt5_plugins').replace('\\', '/')
        os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = qt_plugin_path

        # Указываем путь к QtWebEngineProcess
        webengine_process_path = os.path.join(base_path, 'bin', 'QtWebEngineProcess.exe').replace('\\', '/')
        os.environ['QTWEBENGINEPROCESS_PATH'] = webengine_process_path


def setup_qt_paths():
    """Настройка путей для Qt в собранном приложении"""
    if getattr(sys, 'frozen', False):
        # Если приложение собрано в exe
        base_path = sys._MEIPASS

        # Добавляем пути к Qt в PATH
        qt_paths = [
            os.path.join(base_path, 'bin'),
            os.path.join(base_path, 'plugins'),
            os.path.join(base_path, 'resources'),
        ]

        for path in qt_paths:
            if os.path.exists(path) and path not in os.environ['PATH']:
                os.environ['PATH'] = path + os.pathsep + os.environ['PATH']

        # Указываем путь к QtWebEngineProcess
        webengine_process = os.path.join(base_path, 'QtWebEngineProcess.exe')
        if os.path.exists(webengine_process):
            os.environ['QTWEBENGINEPROCESS_PATH'] = webengine_process

        # Указываем путь к ресурсам
        os.environ['QTWEBENGINE_RESOURCES_PATH'] = os.path.join(base_path, 'resources')


# Вызываем ДО импорта PyQt
setup_qt_paths()

# Вызовите эту функцию до создания QApplication


def debug_qt_paths():
    print("=== QT DEBUG INFO ===")
    print("Frozen:", getattr(sys, 'frozen', False))

    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
        print("MEIPASS:", base_path)

        # Проверяем критические файлы
        files_to_check = [
            'QtWebEngineProcess.exe',
            'resources/icudtl.dat',
            'resources/qtwebengine_resources.pak'
        ]

        for file in files_to_check:
            full_path = os.path.join(base_path, file)
            exists = os.path.exists(full_path)
            print(f"✓ {file}" if exists else f"✗ {file} - MISSING!")

    print("PATH:", os.environ.get('PATH', ''))
    print("QTWEBENGINEPROCESS_PATH:", os.environ.get('QTWEBENGINEPROCESS_PATH', 'Not set'))


def fix_qt_dll():
    # Добавляем пути к DLL PyQt5 в PATH
    venv_path = os.path.dirname(sys.executable)
    site_packages = os.path.join(venv_path, "..", "Lib", "site-packages", "PyQt5", "Qt5", "bin")

    if os.path.exists(site_packages):
        os.environ['PATH'] = site_packages + os.pathsep + os.environ['PATH']
        print(f"Добавлен путь: {site_packages}")

    # Проверяем доступность DLL
    try:
        from PyQt5 import QtCore
        print("✓ PyQt5 загружен успешно!")
        return True
    except ImportError as e:
        print(f"✗ Ошибка: {e}")
        return False


fix_qt_dll()
debug_qt_paths()
set_qt_plugin_path()

def setup_qt_webengine():
    """Настройка путей для Qt WebEngine в виртуальном окружении"""

    # Настройка логирования для отладки
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    if getattr(sys, 'frozen', False):
        # Режим exe - используем MEIPASS
        base_path = sys._MEIPASS
        logger.info(f"Running in frozen mode, MEIPASS: {base_path}")
    else:
        # Режим разработки - используем пути виртуального окружения
        try:
            from PyQt5.QtCore import QLibraryInfo
            base_path = QLibraryInfo.location(QLibraryInfo.PrefixPath)
            logger.info(f"Running in dev mode, Qt path: {base_path}")
        except ImportError:
            logger.error("PyQt5 not found in virtual environment!")
            return False

    # Проверяем и настраиваем критические пути
    webengine_process = os.path.join(base_path, 'bin', 'QtWebEngineProcess.exe')
    resources_path = os.path.join(base_path, 'resources')
    translations_path = os.path.join(base_path, 'translations')

    # Проверяем существование файлов
    if os.path.exists(webengine_process):
        os.environ['QTWEBENGINEPROCESS_PATH'] = webengine_process
        logger.info(f"Set QTWEBENGINEPROCESS_PATH: {webengine_process}")
    else:
        logger.warning(f"QtWebEngineProcess.exe not found at: {webengine_process}")

    if os.path.exists(resources_path):
        os.environ['QTWEBENGINE_RESOURCES_PATH'] = resources_path
        logger.info(f"Set QTWEBENGINE_RESOURCES_PATH: {resources_path}")

    # Добавляем bin в PATH
    bin_path = os.path.join(base_path, 'bin')
    if os.path.exists(bin_path) and bin_path not in os.environ['PATH']:
        os.environ['PATH'] = bin_path + os.pathsep + os.environ['PATH']
        logger.info(f"Added to PATH: {bin_path}")

    return True

# Инициализация ДО импорта PyQt
if not setup_qt_webengine():
    print("Failed to setup Qt WebEngine paths!")
    sys.exit(1)

# Теперь безопасно импортируем PyQt
try:
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtWebEngineWidgets import QWebEngineView
    from PyQt5.QtCore import QUrl
except ImportError as e:
    print(f"Failed to import PyQt5: {e}")
    print("Make sure PyQt5 and PyQtWebEngine are installed in your virtual environment!")
    sys.exit(1)


import base64
import binascii
import json
from pathlib import Path
from PyQt5.QtCore import QObject, pyqtSlot, QUrl, Qt, pyqtSignal, QThread
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QMessageBox, QSizePolicy, QStatusBar, QDialog,
                             QLabel, QSpinBox, QDialogButtonBox, QLineEdit, QProgressBar,
                             QGridLayout, QGroupBox)
from PyQt5.QtWebEngineWidgets import QWebEngineView
import uuid
import subprocess

from tile_manager import TileManager

# Глобальные переменные для директорий
base_dir = Path(__file__).parent
data_dir = os.path.join(base_dir, "data")
file_dir = os.path.join(data_dir, "files")
resources_dir = os.path.join(base_dir, "html_templates")

os.makedirs(data_dir, exist_ok=True)
os.makedirs(file_dir, exist_ok=True)
os.makedirs(resources_dir, exist_ok=True)

# Создание офлайн-ассетов
try:
    import create_offline_assets

    print("Создание офлайн-ассетов...")
    create_offline_assets.create_offline_assets()
    print("Офлайн-ассеты созданы успешно")
except Exception as e:
    print(f"Ошибка создания ассетов: {e}")


class DownloadThread(QThread):
    finished = pyqtSignal(int)
    progress = pyqtSignal(int, int)

    def __init__(self, tile_manager, bounds, zoom_levels, name, visible_area=False):
        super().__init__()
        self.tile_manager = tile_manager
        self.bounds = bounds
        self.zoom_levels = zoom_levels
        self.name = name
        self.visible_area = visible_area
        self._is_running = True

    def stop(self):
        self._is_running = False

    def run(self):
        try:
            if self.visible_area:
                # Для видимой области используем специальный метод
                tiles_downloaded = self.tile_manager.download_visible_area(
                    self.bounds, self.zoom_levels, self.name, self.progress, self
                )
            else:
                # Для обычной области
                tiles_downloaded = self.tile_manager.download_area(
                    self.bounds, self.zoom_levels, self.name, self.progress, self
                )
            self.finished.emit(tiles_downloaded)
        except Exception as e:
            print(f"Ошибка загрузки: {e}")
            self.finished.emit(0)


class DataManager():
    def __init__(self, data_path):
        self.data_path = data_path
        self.data_file = os.path.join(data_path, "data.json")
        self.current_data = []
        self.ensure_data_file()
        self.load_data()

    def ensure_data_file(self):
        """Создает файл данных и директорию, если они не существуют"""
        os.makedirs(self.data_path, exist_ok=True)
        if not os.path.exists(self.data_file):
            self.save_data()

    def load_data(self):
        """Загружает данные из файла"""
        try:
            with open(self.data_file, 'r', encoding='utf-8') as file:
                self.current_data = json.load(file)
        except (json.JSONDecodeError, FileNotFoundError):
            self.current_data = []

    def save_data(self):
        """Сохраняет данные в файл"""
        with open(self.data_file, "w", encoding="utf-8") as file:
            json.dump(self.current_data, file, ensure_ascii=False, indent=4)

    def add_point(self, point_data):
        """Добавляет точку с уникальным ID"""
        point_data['id'] = str(uuid.uuid4())
        self.current_data.append(point_data)
        self.save_data()
        return point_data['id']

    def remove_point(self, point_id):
        point = next((p for p in self.current_data if p.get('id') == point_id), None)
        if not point:
            print(f"Точка с ID {point_id} не найдена.")
            return

        file_names = point.get('fileNames', [])
        if not file_names:
            single_file = point.get('fileName')
            if single_file and single_file not in [None, 'Null']:
                file_names = [single_file]

        for file_name in file_names:
            can_delete_file = all(
                file_name not in p.get('fileNames', []) and
                file_name != p.get('fileName')
                for p in self.current_data
                if p.get('id') != point_id
            )

            if can_delete_file:
                try:
                    file_path = os.path.join(file_dir, file_name)
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        print(f"Файл '{file_path}' удален.")
                except OSError as e:
                    print(f"Ошибка при удалении файла: {e}")

        self.current_data = [p for p in self.current_data if p.get('id') != point_id]
        self.save_data()

    def clear_all_points(self):
        """Удаляет все точки"""
        self.current_data = []
        self.save_data()

    def update_points(self, points_data):
        """Обновляет все точки"""
        self.current_data = points_data
        self.save_data()

    def search_points(self, query):
        """Ищет точки по запросу"""
        if not query:
            return self.current_data

        query = query.lower()
        results = []
        for point in self.current_data:
            if (query in point.get('name', '').lower() or
                    query in point.get('deep', '').lower() or
                    query in point.get('filters', '').lower() or
                    query in point.get('debit', '').lower() or
                    query in point.get('comments', '').lower() or
                    any(query in fname.lower() for fname in point.get('fileNames', []))):
                results.append(point)

        return results


class Bridge(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent

    @pyqtSlot(float, float)
    def addPoint(self, lat, lng):
        self.parent.add_point(lat, lng)

    @pyqtSlot(str)
    def removePoint(self, point_id):
        self.parent.remove_point(point_id)

    @pyqtSlot(str)
    def changeColor(self, json_data):
        try:
            data = json.loads(json_data)
            self.parent.update_color(data)
        except json.JSONDecodeError as e:
            print(f"Ошибка parsing JSON: {e}")

    @pyqtSlot(str)
    def openFileInWord(self, fileName):
        """Открывает файл в Word"""
        try:
            file_path = os.path.join(file_dir, fileName)
            if os.path.exists(file_path):
                if sys.platform == "win32":
                    os.startfile(file_path)
                else:
                    if sys.platform == "darwin":
                        subprocess.call(('open', file_path))
                    else:
                        subprocess.call(('xdg-open', file_path))
                self.parent.statusBar().showMessage(f"Открытие файла: {fileName}")
            else:
                self.parent.statusBar().showMessage(f"Файл не найден: {fileName}")
        except Exception as e:
            print(f"Ошибка при открытии файла: {e}")
            self.parent.statusBar().showMessage(f"Ошибка при открытии файла: {fileName}")

    @pyqtSlot(str, result=str)
    def getTile(self, url):
        """Возвращает тайл в формате Data URL"""
        try:
            result = self.parent.tile_manager.get_tile_data_url(url)
            return result or ""
        except Exception as e:
            print(f"Ошибка в getTile: {e}")
            return ""

    @pyqtSlot(result=str)
    def getOfflineStats(self):
        """Возвращает статистику офлайн-карт в формате JSON"""
        try:
            stats = self.parent.tile_manager.get_stats()
            return json.dumps(stats)
        except Exception as e:
            print(f"Ошибка в getOfflineStats: {e}")
            return json.dumps({"error": str(e)})

    @pyqtSlot()
    def switchToOfflineMode(self):
        """Принудительно переключает в офлайн-режим"""
        self.parent.force_offline_mode()

    @pyqtSlot()
    def switchToOnlineMode(self):
        """Переключает в онлайн-режим"""
        self.parent.force_online_mode()

    @pyqtSlot(result=str)
    def getCurrentMapBounds(self):
        """Возвращает текущие границы карты в формате JSON"""
        try:
            bounds = self.parent.get_current_map_bounds()
            return json.dumps(bounds) if bounds else "null"
        except Exception as e:
            print(f"Ошибка получения границ карты: {e}")
            return "null"

    @pyqtSlot(result=int)
    def getCurrentZoom(self):
        """Возвращает текущий zoom уровень карты"""
        try:
            return self.parent.get_current_zoom()
        except Exception as e:
            print(f"Ошибка получения zoom уровня: {e}")
            return 12


class MapApp(QMainWindow):
    def __init__(self, data_manager):
        super().__init__()
        self.data_manager = data_manager
        self.points = data_manager.current_data
        self.point_mode = False
        self.tile_manager = TileManager(data_dir)
        self.download_thread = None
        self.current_mode = "offline"

        # Переменные для хранения текущего состояния карты
        self.current_bounds = None
        self.current_zoom = 12

        self.setup_ui()
        self.setup_web_channel()

    def setup_ui(self):
        """Настраивает пользовательский интерфейс"""
        self.setWindowTitle("Карта скважин - CartoDB Voyager (Офлайн режим)")
        self.resize(1200, 800)
        self.center_window()

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        self.map_view = QWebEngineView()
        self.map_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.map_view, 1)

        self.statusBar().showMessage("CartoDB Voyager - Готово (Офлайн режим)")

        self.load_map_html()
        self.setup_toolbar(layout)

    def center_window(self):
        """Центрирует окно на экране"""
        frame_geometry = self.frameGeometry()
        center_point = QApplication.primaryScreen().availableGeometry().center()
        frame_geometry.moveCenter(center_point)
        self.move(frame_geometry.topLeft())

    def setup_toolbar(self, layout):
        """Создает панель инструментов с офлайн-функциями"""
        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)

        # Основные кнопки
        self.btn_add_point = QPushButton("Добавить точку")
        self.btn_add_point.clicked.connect(self.enable_add_point_mode)
        self.btn_del_point = QPushButton("Удалить выбранные точки")
        self.btn_del_point.clicked.connect(self.remove_selected_points)

        # Офлайн-функции
        self.btn_download_map = QPushButton("Скачать офлайн-карту")
        self.btn_download_map.clicked.connect(self.download_offline_map)

        self.btn_download_visible = QPushButton("Скачать видимую область")
        self.btn_download_visible.clicked.connect(self.download_visible_area)

        self.btn_offline_stats = QPushButton("Статистика офлайн-карт")
        self.btn_offline_stats.clicked.connect(self.show_offline_stats)

        self.btn_clear_cache = QPushButton("Очистить кэш")
        self.btn_clear_cache.clicked.connect(self.clear_offline_cache)

        buttons = [
            self.btn_add_point,
            self.btn_del_point,
            self.btn_download_map,
            self.btn_download_visible,
            self.btn_offline_stats,
            self.btn_clear_cache
        ]

        for btn in buttons:
            btn.setMinimumHeight(35)
            btn.setMinimumWidth(160)
            btn.setStyleSheet("""
QPushButton {
    padding: 8px 12px;
    background: #4361ee;
    color: white;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    font-weight: bold;
    transition: background 0.2s;
}
QPushButton:hover {
    background-color: #2980b9;
}
QPushButton:pressed {
    background-color: #1c6ea4;
}
""")
            toolbar_layout.addWidget(btn)

        toolbar_layout.addStretch()
        layout.addWidget(toolbar)

    def remove_selected_points(self):
        self.map_view.page().runJavaScript(f"removeSelectedPoints();")

    def setup_web_channel(self):
        """Настраивает WebChannel для связи с JavaScript"""
        self.bridge = Bridge(self)
        self.channel = QWebChannel()
        self.channel.registerObject('bridge', self.bridge)
        self.map_view.page().setWebChannel(self.channel)

    def load_map_html(self):
        """Загружает HTML карты с встроенными данными"""
        try:
            html_template = self.read_file("map_template.html")
            if not html_template:
                QMessageBox.critical(self, "Ошибка", "Не удалось загрузить шаблон карты")
                return

            points_json = json.dumps(self.points, ensure_ascii=False)
            html_content = html_template.replace('/* {{POINTS_DATA}} */', f'var initialMarkerData = {points_json};')

            base_url = QUrl.fromLocalFile(str(resources_dir) + "/")
            self.map_view.setHtml(html_content, base_url)

            self.map_view.loadFinished.connect(self.on_map_loaded)

        except Exception as e:
            print(f"Ошибка загрузки карты: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить карту: {str(e)}")

    def read_file(self, filename):
        """Читает файл из директории ресурсов"""
        try:
            file_path = os.path.join(resources_dir, filename)
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"Ошибка чтения файла {filename}: {e}")
            return None

    def on_map_loaded(self):
        """Вызывается после загрузки карты"""
        print("Карта загружена, инициализация точек...")
        self.map_view.page().runJavaScript("initPoints();")

    def get_current_map_bounds(self):
        """Получает текущие границы карты через JavaScript"""
        return self.current_bounds

    def get_current_zoom(self):
        """Получает текущий zoom уровень карты"""
        return self.current_zoom

    def enable_add_point_mode(self):
        """Активирует режим добавления точки"""
        if self.point_mode == False:
            self.statusBar().showMessage("Режим добавления: кликните на карту")
            self.point_mode = True
            self.map_view.page().runJavaScript("enableClickHandler();")
            self.btn_add_point.setStyleSheet("""
                QPushButton {
                    padding: 8px 12px;
                    background: #1c6ea4;
                    color: white;
                    border: none;
                    border-radius: 6px;
                    cursor: pointer;
                    font-weight: bold;
                    width: 100%;
                    transition: background 0.2s;
                }
                QPushButton:hover {
                    background-color: #2980b9;
                }
                QPushButton:pressed {
                    background-color: #1c6ea4;
                }
            """)
        else:
            self.statusBar().showMessage("Отмена режима добавления точки")
            self.point_mode = False
            self.map_view.page().runJavaScript("disableClickHandler();")
            self.btn_add_point.setStyleSheet("""
                QPushButton {
                    padding: 8px 12px;
                    background: #4361ee;
                    color: white;
                    border: none;
                    border-radius: 6px;
                    cursor: pointer;
                    font-weight: bold;
                    width: 100%;
                    transition: background 0.2s;
                }
                QPushButton:hover {
                    background-color: #2980b9;
                }
                QPushButton:pressed {
                    background-color: #1c6ea4;
                }
            """)

    def add_point(self, lat, lng):
        if not self.point_mode:
            return

        self.dialog_window = DialogWindow(self)
        self.dialog_window.dataSubmitted.connect(
            lambda data: self.process_point_data(lat, lng, data)
        )
        self.dialog_window.destroyed.connect(
            lambda: self.cancel_point_addition()
        )
        self.dialog_window.show()

    def process_point_data(self, lat, lng, data):
        new_point = {
            "lat": lat,
            "lng": lng,
            "name": data.get("name"),
            "deep": data.get("deep"),
            "filters": data.get("filters"),
            "debit": data.get("debit"),
            "comments": data.get("comments"),
            "color": data.get("color", "#4361ee"),
            "fileNames": data.get("fileNames", []),
            "fileName": data.get("fileNames", [""])[0] if data.get("fileNames") else ""
        }

        point_id = self.data_manager.add_point(new_point)

        js_code = f"""
        addMarker(
            {lat}, 
            {lng},
            {json.dumps(new_point['name'])}, 
            '{point_id}',
            {json.dumps(new_point['deep'])},
            {json.dumps(new_point['filters'])},
            {json.dumps(new_point['debit'])},
            {json.dumps(new_point['comments'])},
            {json.dumps(new_point['color'])},
            {json.dumps(new_point['fileName'])},
            {json.dumps(new_point['fileNames'])}
        );
        """
        self.map_view.page().runJavaScript(js_code)
        self.statusBar().showMessage(f"Добавлена точка: {new_point['name']} с {len(new_point['fileNames'])} файлами")
        self.map_view.page().runJavaScript("disableClickHandler();")
        self.points = self.data_manager.current_data
        self.dialog_window.close()
        self.point_mode = False

    def cancel_point_addition(self):
        self.statusBar().showMessage("Добавление точки отменено")
        self.point_mode = False
        self.map_view.page().runJavaScript("disableClickHandler();")

    def remove_point(self, point_id):
        point = next((p for p in self.points if p.get('id') == point_id), None)
        if point:
            file_count = len(point.get('fileNames', []))
            file_text = f" с {file_count} файлами" if file_count > 0 else ""

            reply = QMessageBox.question(
                self, "Подтверждение",
                f"Вы действительно хотите удалить точку '{point['name']}'{file_text}?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.data_manager.remove_point(point_id)
                self.map_view.page().runJavaScript(f"removeMarker('{point_id}');")
                self.statusBar().showMessage(f"Точка '{point['name']}' удалена")

    def clear_map(self):
        reply = QMessageBox.question(
            self, "Подтверждение",
            "Вы действительно хотите очистить карту и удалить все точки?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.data_manager.clear_all_points()
            self.map_view.page().runJavaScript("clearMarkers();")
            self.statusBar().showMessage("Все точки удалены")
            self.point_mode = False

    def update_color(self, points_data):
        try:
            points_dict = {point['id']: point for point in self.data_manager.current_data}

            for point in points_data:
                if point['id'] in points_dict:
                    points_dict[point['id']]['color'] = point.get('color', '#4361ee')

            self.data_manager.current_data = list(points_dict.values())
            self.data_manager.save_data()
            self.points = self.data_manager.current_data

            self.statusBar().showMessage("Цвета маркеров успешно обновлены")
        except Exception as e:
            print(f"Ошибка при обновлении цветов: {e}")
            self.statusBar().showMessage("Ошибка при обновлении цветов маркеров")

    # ОФЛАЙН-ФУНКЦИИ
    def download_offline_map(self):
        """Диалог для скачивания офлайн-карты по всем точкам"""
        if self.points:
            lats = [p['lat'] for p in self.points]
            lngs = [p['lng'] for p in self.points]
            bounds = [min(lats), min(lngs), max(lats), max(lngs)]
        else:
            bounds = [59.8, 30.1, 60.1, 30.5]

        self.show_download_dialog(bounds, "CartoDB Voyager - Моя офлайн карта")

    def download_visible_area(self):
        """Скачивает только видимую область карты"""
        # Получаем текущие границы карты через JavaScript
        js_code = """
        var bounds = map.getBounds();
        var zoom = map.getZoom();
        JSON.stringify({
            north: bounds.getNorth(),
            south: bounds.getSouth(), 
            east: bounds.getEast(),
            west: bounds.getWest(),
            zoom: zoom
        });
        """

        def handle_bounds(result):
            try:
                bounds_data = json.loads(result)
                bounds = [
                    bounds_data['south'],
                    bounds_data['west'],
                    bounds_data['north'],
                    bounds_data['east']
                ]
                current_zoom = bounds_data['zoom']

                # Показываем диалог для подтверждения загрузки видимой области
                self.show_visible_area_dialog(bounds, current_zoom)

            except Exception as e:
                print(f"Ошибка получения границ карты: {e}")
                QMessageBox.warning(self, "Ошибка", "Не удалось получить границы карты")

        self.map_view.page().runJavaScript(js_code, handle_bounds)

    def show_visible_area_dialog(self, bounds, current_zoom):
        """Показывает диалог для загрузки видимой области с выбором zoom слоев"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Скачать видимую область CartoDB Voyager")
        dialog.setFixedSize(500, 450)
        layout = QVBoxLayout(dialog)

        # Информация о текущей области
        info_group = QGroupBox("Информация о видимой области")
        info_layout = QGridLayout(info_group)

        info_layout.addWidget(QLabel("Текущий zoom:"), 0, 0)
        info_layout.addWidget(QLabel(f"{current_zoom}"), 0, 1)

        info_layout.addWidget(QLabel("Границы:"), 1, 0)
        bounds_label = QLabel(f"{bounds[0]:.4f}, {bounds[1]:.4f}, {bounds[2]:.4f}, {bounds[3]:.4f}")
        bounds_label.setWordWrap(True)
        info_layout.addWidget(bounds_label, 1, 1)

        layout.addWidget(info_group)

        # Выбор zoom слоев
        zoom_group = QGroupBox("Выбор zoom слоев для скачивания")
        zoom_layout = QGridLayout(zoom_group)

        zoom_layout.addWidget(QLabel("Минимальный zoom:"), 0, 0)
        min_zoom = QSpinBox()
        min_zoom.setRange(0, 18)
        min_zoom.setValue(max(0, current_zoom - 2))
        min_zoom.valueChanged.connect(lambda: self.update_zoom_range(min_zoom, max_zoom))
        zoom_layout.addWidget(min_zoom, 0, 1)

        zoom_layout.addWidget(QLabel("Максимальный zoom:"), 1, 0)
        max_zoom = QSpinBox()
        max_zoom.setRange(0, 18)
        max_zoom.setValue(min(18, current_zoom + 2))
        max_zoom.valueChanged.connect(lambda: self.update_zoom_range(min_zoom, max_zoom))
        zoom_layout.addWidget(max_zoom, 1, 1)

        zoom_layout.addWidget(QLabel("Количество слоев:"), 2, 0)
        zoom_count_label = QLabel(f"{max_zoom.value() - min_zoom.value() + 1}")
        zoom_layout.addWidget(zoom_count_label, 2, 1)

        # Список выбранных zoom уровней
        zoom_layout.addWidget(QLabel("Выбранные zoom:"), 3, 0)
        zoom_list_label = QLabel(self.get_zoom_list_text(min_zoom.value(), max_zoom.value()))
        zoom_list_label.setWordWrap(True)
        zoom_layout.addWidget(zoom_list_label, 3, 1)

        layout.addWidget(zoom_group)

        # Название и информация о размере
        layout.addWidget(QLabel("Название области:"))
        name_input = QLineEdit(f"CartoDB Voyager - Видимая область (zoom {min_zoom.value()}-{max_zoom.value()})")
        layout.addWidget(name_input)

        # Динамическое обновление оценки размера
        estimated_size = self.tile_manager.estimate_download_size(bounds,
                                                                  list(range(min_zoom.value(), max_zoom.value() + 1)))
        size_label = QLabel(f"Примерный размер: {estimated_size} МБ")
        layout.addWidget(size_label)

        # Функция для обновления размера при изменении zoom
        def update_size():
            zoom_levels = list(range(min_zoom.value(), max_zoom.value() + 1))
            estimated_size = self.tile_manager.estimate_download_size(bounds, zoom_levels)
            size_label.setText(f"Примерный размер: {estimated_size} МБ")
            zoom_count_label.setText(f"{len(zoom_levels)}")
            zoom_list_label.setText(self.get_zoom_list_text(min_zoom.value(), max_zoom.value()))
            name_input.setText(f"CartoDB Voyager - Видимая область (zoom {min_zoom.value()}-{max_zoom.value()})")

        min_zoom.valueChanged.connect(update_size)
        max_zoom.valueChanged.connect(update_size)

        info_label = QLabel("Будут загружены тайлы для выбранных zoom уровней в пределах видимой области.")
        info_label.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(info_label)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec_() == QDialog.Accepted:
            zoom_levels = list(range(min_zoom.value(), max_zoom.value() + 1))
            self.start_download(bounds, zoom_levels, name_input.text(), True)

    def update_zoom_range(self, min_zoom, max_zoom):
        """Обновляет диапазон zoom уровней"""
        if min_zoom.value() > max_zoom.value():
            max_zoom.setValue(min_zoom.value())

    def get_zoom_list_text(self, min_zoom, max_zoom):
        """Возвращает текстовое представление выбранных zoom уровней"""
        if max_zoom - min_zoom <= 5:
            return ", ".join(map(str, range(min_zoom, max_zoom + 1)))
        else:
            return f"{min_zoom}-{max_zoom}"

    def show_download_dialog(self, bounds, default_name):
        """Показывает диалог для скачивания офлайн-карты"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Скачать офлайн-карту CartoDB Voyager")
        dialog.setFixedSize(400, 350)
        layout = QVBoxLayout(dialog)

        layout.addWidget(QLabel("Область карты:"))

        bounds_label = QLabel(f"Границы: {bounds[0]:.4f}, {bounds[1]:.4f}, {bounds[2]:.4f}, {bounds[3]:.4f}")
        layout.addWidget(bounds_label)

        layout.addWidget(QLabel("Минимальный zoom:"))
        min_zoom = QSpinBox()
        min_zoom.setRange(0, 18)
        min_zoom.setValue(10)
        layout.addWidget(min_zoom)

        layout.addWidget(QLabel("Максимальный zoom:"))
        max_zoom = QSpinBox()
        max_zoom.setRange(0, 18)
        max_zoom.setValue(15)
        layout.addWidget(max_zoom)

        layout.addWidget(QLabel("Название области:"))
        name_input = QLineEdit(default_name)
        layout.addWidget(name_input)

        estimated_size = self.tile_manager.estimate_download_size(bounds,
                                                                  list(range(min_zoom.value(), max_zoom.value() + 1)))
        size_label = QLabel(f"Примерный размер: {estimated_size} МБ")
        layout.addWidget(size_label)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec_() == QDialog.Accepted:
            zoom_levels = list(range(min_zoom.value(), max_zoom.value() + 1))
            self.start_download(bounds, zoom_levels, name_input.text(), False)

    def start_download(self, bounds, zoom_levels, name, is_visible_area):
        """Запускает процесс загрузки тайлов"""
        progress_dialog = QDialog(self)
        if is_visible_area:
            progress_dialog.setWindowTitle("Загрузка видимой области CartoDB Voyager")
        else:
            progress_dialog.setWindowTitle("Загрузка офлайн-карты CartoDB Voyager")

        progress_dialog.setFixedSize(400, 150)
        progress_layout = QVBoxLayout(progress_dialog)

        if is_visible_area:
            progress_label = QLabel(f"Загрузка видимой области ({len(zoom_levels)} zoom слоев)...")
        else:
            progress_label = QLabel(f"Загрузка тайлов CartoDB Voyager ({len(zoom_levels)} zoom слоев)...")
        progress_layout.addWidget(progress_label)

        progress_bar = QProgressBar()
        progress_bar.setRange(0, 100)
        progress_layout.addWidget(progress_bar)

        progress_text = QLabel("Подготовка к загрузке...")
        progress_layout.addWidget(progress_text)

        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(lambda: self.cancel_download(progress_dialog))
        progress_layout.addWidget(cancel_btn)

        progress_dialog.show()

        self.download_thread = DownloadThread(
            self.tile_manager, bounds, zoom_levels, name, is_visible_area
        )
        self.download_thread.progress.connect(
            lambda current, total: self.on_download_progress(current, total, progress_bar, progress_text)
        )
        self.download_thread.finished.connect(
            lambda count: self.on_download_finished(count, progress_dialog, is_visible_area, zoom_levels)
        )
        self.download_thread.start()

    def cancel_download(self, progress_dialog):
        """Отменяет загрузку"""
        if self.download_thread and self.download_thread.isRunning():
            self.download_thread.stop()
            self.download_thread.wait(1000)
        progress_dialog.close()
        self.statusBar().showMessage("Загрузка отменена")

    def on_download_progress(self, current, total, progress_bar, progress_label):
        """Обновляет прогресс загрузки"""
        if total > 0:
            progress = int((current / total) * 100)
            progress_bar.setValue(progress)
            progress_label.setText(f"Загружено: {current} из {total} тайлов ({progress}%)")

    def on_download_finished(self, tiles_downloaded, progress_dialog, is_visible_area, zoom_levels):
        """Вызывается после завершения загрузки"""
        progress_dialog.close()

        if tiles_downloaded > 0:
            if is_visible_area:
                message = f"Загружено {tiles_downloaded} тайлов видимой области ({len(zoom_levels)} zoom слоев)"
            else:
                message = f"Загружено {tiles_downloaded} тайлов CartoDB Voyager ({len(zoom_levels)} zoom слоев)"

            QMessageBox.information(self, "Загрузка завершена", message)
            self.statusBar().showMessage(message)
        else:
            QMessageBox.information(
                self,
                "Загрузка завершена",
                "Все тайлы уже загружены в кэш"
            )

    def show_offline_stats(self):
        """Показывает статистику офлайн-карт"""
        stats = self.tile_manager.get_stats()

        stats_text = f"""
        CartoDB Voyager - Офлайн карты:
        Всего тайлов: {stats['total_tiles']}
        Областей: {len(stats['tilesets'])}
        Размер кэша: {stats['total_size_mb']} MB

        Доступные области:
        """

        for name, info in stats['tilesets'].items():
            stats_text += f"\n- {name}: zoom {info['min_zoom']}-{info['max_zoom']}"

        if not stats['tilesets']:
            stats_text += "\nНет сохраненных областей"

        QMessageBox.information(self, "Статистика офлайн-карт CartoDB Voyager", stats_text)

    def clear_offline_cache(self):
        """Очищает кэш офлайн-карт"""
        reply = QMessageBox.question(
            self, "Подтверждение",
            "Вы действительно хотите очистить кэш офлайн-карт CartoDB Voyager?\nВсе скачанные тайлы будут удалены.",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            if self.tile_manager.clear_cache():
                QMessageBox.information(self, "Успех", "Кэш офлайн-карт CartoDB Voyager очищен")
                self.statusBar().showMessage("Кэш офлайн-карт CartoDB Voyager очищен")
            else:
                QMessageBox.warning(self, "Ошибка", "Не удалось очистить кэш")

    def force_offline_mode(self):
        """Принудительно переключает в офлайн-режим"""
        self.current_mode = "offline"
        self.map_view.page().runJavaScript("switchToOfflineLayer();")
        self.statusBar().showMessage("CartoDB Voyager - Офлайн режим активирован")

    def force_online_mode(self):
        """Переключает в онлайн-режим"""
        self.current_mode = "online"
        self.map_view.page().runJavaScript("switchToOnlineLayer();")
        self.statusBar().showMessage("CartoDB Voyager - Онлайн режим активирован")


class DialogBridge(QObject):
    formDataSubmitted = pyqtSignal(dict)

    @pyqtSlot(str)
    def sendFormData(self, json_data):
        try:
            data = json.loads(json_data)
            print("Получены данные формы:", data.keys())

            files_data = data.get('files', [])
            saved_file_names = []

            for file_item in files_data:
                file_data = file_item.get('fileData')
                file_name = file_item.get('fileName')
                file_size = file_item.get('fileSize', 0)
                if file_data:
                    try:
                        if file_data == 'data:':
                            base64_data = b''
                        else:
                            if file_data.startswith('data:'):
                                base64_data = file_data.split(',', 1)[1]
                            else:
                                base64_data = file_data
                        print(base64_data)
                        file_bytes = base64.b64decode(base64_data)
                        print(f"Файл '{file_name}' успешно декодирован, размер: {len(file_bytes)} байт")

                        base_name, extension = os.path.splitext(file_name)
                        unique_name = f"{base_name}_{uuid.uuid4().hex[:8]}{extension}"

                        print(unique_name)
                        file_path = os.path.join(file_dir, unique_name)
                        with open(file_path, 'wb') as f:
                            f.write(file_bytes)

                        print(f"Файл сохранен как: {file_path}")
                        saved_file_names.append(unique_name)

                    except (binascii.Error, Exception) as e:
                        print(f"Ошибка обработки файла '{file_name}': {e}")
                else:
                    print(f"Пропущен файл '{file_name}': отсутствуют данные")

            data['fileNames'] = saved_file_names
            self.formDataSubmitted.emit(data)

        except json.JSONDecodeError as e:
            print(f"Ошибка parsing JSON: {e}")


class DialogWindow(QMainWindow):
    dataSubmitted = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Point input window")
        self.resize(550, 950)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        self.form = QWebEngineView()
        self.form.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        layout.addWidget(self.form, 1)
        self.setup_web_channel()
        self.load_template()

    def load_template(self):
        html_template = self.read_file("form_template.html")

        if not html_template:
            QMessageBox.critical(self, "Ошибка", "Не удалось загрузить шаблон ввода")
            return

        self.form.setHtml(html_template, QUrl.fromLocalFile(str(resources_dir)))

    def read_file(self, filename):
        """Читает файл из директории ресурсов"""
        try:
            file_path = os.path.join(resources_dir, filename)
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"Ошибка чтения файла {filename}: {e}")
            return None

    def setup_web_channel(self):
        self.bridge = DialogBridge(self)
        self.bridge.formDataSubmitted.connect(self.dataSubmitted)
        self.channel = QWebChannel()
        self.channel.registerObject('dialogBridge', self.bridge)
        self.form.page().setWebChannel(self.channel)


if __name__ == "__main__":
    data_manager = DataManager(data_dir)

    app = QApplication(sys.argv)
    window = MapApp(data_manager)
    window.show()
    sys.exit(app.exec_())