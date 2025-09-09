import sys
import os
import base64
import binascii
import json
from pathlib import Path
from PyQt5.QtCore import QObject, pyqtSlot, QUrl, Qt, pyqtSignal
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QMessageBox, QSizePolicy, QStatusBar)
from PyQt5.QtWebEngineWidgets import QWebEngineView
import uuid
import subprocess

# Глобальные переменные для директорий
base_dir = Path(__file__).parent
data_dir = os.path.join(base_dir, "data")
file_dir = os.path.join(data_dir, "files")
resources_dir = os.path.join(base_dir, "html_templates")

os.makedirs(data_dir, exist_ok=True)
os.makedirs(file_dir, exist_ok=True)
os.makedirs(resources_dir, exist_ok=True)


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

        file_name = point.get('fileName')
        # Проверяем, используется ли файл другими точками
        can_delete_file = all(
            file_name != p.get('fileName')
            for p in self.current_data
            if p.get('id') != point_id
        ) and file_name not in (None, 'Null')

        # Удаляем точку
        self.current_data = [p for p in self.current_data if p.get('id') != point_id]

        if can_delete_file:
            try:
                file_path = os.path.join(file_dir, file_name)
                os.remove(file_path)
                print(f"Файл '{file_path}' удален.")
            except OSError as e:
                print(f"Ошибка при удалении файла: {e}")

        self.save_data()  # Сохраняем данные в любом случае

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
                    query in point.get('fileName', '').lower()):
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
                # Для Windows используем os.startfile
                if sys.platform == "win32":
                    os.startfile(file_path)
                else:
                    # Для других платформ используем subprocess
                    if sys.platform == "darwin":  # macOS
                        subprocess.call(('open', file_path))
                    else:  # Linux
                        subprocess.call(('xdg-open', file_path))
                self.parent.statusBar().showMessage(f"Открытие файла: {fileName}")
            else:
                self.parent.statusBar().showMessage(f"Файл не найден: {fileName}")
        except Exception as e:
            print(f"Ошибка при открытии файла: {e}")
            self.parent.statusBar().showMessage(f"Ошибка при открытии файла: {fileName}")


class MapApp(QMainWindow):
    def __init__(self, data_manager):
        super().__init__()
        self.data_manager = data_manager
        self.points = data_manager.current_data
        self.point_mode = False

        self.setup_ui()
        self.setup_web_channel()

    def setup_ui(self):
        """Настраивает пользовательский интерфейс"""
        self.setWindowTitle("Картографическое приложение")
        self.resize(1200, 800)
        self.center_window()

        # Центральный виджет и компоновка
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Создаем карту
        self.map_view = QWebEngineView()
        self.map_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Добавляем карту
        layout.addWidget(self.map_view, 1)

        # Статус бар
        self.statusBar().showMessage("Готово")

        # Загружаем карту
        self.load_map_html()

        # Панель инструментов
        self.setup_toolbar(layout)

    def center_window(self):
        """Центрирует окно на экране"""
        frame_geometry = self.frameGeometry()
        center_point = QApplication.primaryScreen().availableGeometry().center()
        frame_geometry.moveCenter(center_point)
        self.move(frame_geometry.topLeft())

    def setup_toolbar(self, layout):
        """Создает панель инструментов"""
        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)

        self.btn_add_point = QPushButton("Добавить точку")
        self.btn_add_point.clicked.connect(self.enable_add_point_mode)
        self.btn_del_point = QPushButton("Удалить выбранные точки")
        self.btn_del_point.clicked.connect(self.remove_selected_points)

        for btn in [self.btn_add_point,self.btn_del_point]:
            btn.setMinimumHeight(35)
            btn.setMinimumWidth(180)
            btn.setStyleSheet("""
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
            toolbar_layout.addWidget(btn)

        toolbar_layout.addStretch()
        layout.addWidget(toolbar)

    def remove_selected_points(self):
        self.map_view.page().runJavaScript(f"removeSelectedPoints();")
        print("а")
    def setup_web_channel(self):
        """Настраивает WebChannel для связи с JavaScript"""
        self.bridge = Bridge(self)
        self.channel = QWebChannel()
        self.channel.registerObject('bridge', self.bridge)
        self.map_view.page().setWebChannel(self.channel)

    def load_map_html(self):
        """Загружает HTML карты с встроенными данными"""
        # Загружаем базовый HTML шаблон
        html_template = self.read_file("map_template.html")

        if not html_template:
            QMessageBox.critical(self, "Ошибка", "Не удалось загрузить шаблон карты")
            return

        # Вставляем данные точек в HTML
        points_json = json.dumps(self.points, ensure_ascii=False)
        html_content = html_template.replace('/* {{POINTS_DATA}} */', f'var initialMarkerData = {points_json};')

        # Загружаем карту
        self.map_view.setHtml(html_content, QUrl.fromLocalFile(os.path.abspath(".")))

        # Обработчик загрузки карты
        self.map_view.loadFinished.connect(self.on_map_loaded)

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
        # Инициализируем точки на карте
        self.map_view.page().runJavaScript("initPoints();")

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
            "fileName": data.get("fileName")
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
            {json.dumps(new_point['fileName'])}
        );
        """
        self.map_view.page().runJavaScript(js_code)
        self.statusBar().showMessage(f"Добавлена точка: {new_point['name']}")
        self.map_view.page().runJavaScript("disableClickHandler();")
        self.points = self.data_manager.current_data
        self.dialog_window.close()
        self.point_mode = False

    def cancel_point_addition(self):
        self.statusBar().showMessage("Добавление точки отменено")
        self.point_mode = False
        self.map_view.page().runJavaScript("disableClickHandler();")

    def remove_point(self, point_id):
        """Удаляет точку по ID"""
        # Находим точку для отображения информации
        point = next((p for p in self.points if p.get('id') == point_id), None)
        if point:
            reply = QMessageBox.question(
                self, "Подтверждение",
                f"Вы действительно хотите удалить точку '{point['name']}'?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.data_manager.remove_point(point_id)
                self.map_view.page().runJavaScript(f"removeMarker('{point_id}');")
                self.statusBar().showMessage(f"Точка '{point['name']}' удалена")

    def clear_map(self):
        """Очищает карту и данные"""
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
        """Обновляет цвета точек в данных"""
        try:
            # Создаем словарь для быстрого поиска точек по ID
            points_dict = {point['id']: point for point in self.data_manager.current_data}

            # Обновляем цвета
            for point in points_data:
                if point['id'] in points_dict:
                    points_dict[point['id']]['color'] = point.get('color', '#4361ee')

            # Преобразуем обратно в список
            self.data_manager.current_data = list(points_dict.values())
            self.data_manager.save_data()
            self.points = self.data_manager.current_data

            self.statusBar().showMessage("Цвета маркеров успешно обновлены")
        except Exception as e:
            print(f"Ошибка при обновлении цветов: {e}")
            self.statusBar().showMessage("Ошибка при обновлении цветов маркеров")


class DialogBridge(QObject):
    formDataSubmitted = pyqtSignal(dict)

    @pyqtSlot(str)
    def sendFormData(self, json_data):
        try:
            data = json.loads(json_data)
            file_data = data.get('fileData')

            if file_data:
                # Извлекаем base64 данные из Data URL
                if file_data.startswith('data:'):
                    # Разделяем по запятой и берем вторую часть
                    base64_data = file_data.split(',', 1)[1]
                else:
                    # Если это уже чистый base64 (без префикса)
                    base64_data = file_data

                try:
                    # Декодируем base64
                    file_bytes = base64.b64decode(base64_data)
                    print(f"Файл успешно декодирован, размер: {len(file_bytes)} байт")


                    # Сохраняем файл
                    file_name = data.get('fileName', 'document.docx')
                    with open(os.path.join(file_dir, file_name), 'wb') as f:
                        f.write(file_bytes)
                    print(f"Файл сохранен как: {os.path.join(file_dir, file_name)}")

                except binascii.Error as e:
                    print(f"Ошибка декодирования base64: {e}")
                    # Возможно, данные повреждены или имеют неправильный формат

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

        # Центральный виджет и компоновка
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Создаем форму
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

        self.form.setHtml(html_template, QUrl("qrc:/"))

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
    # Создаем менеджер данных
    data_manager = DataManager(data_dir)

    app = QApplication(sys.argv)
    window = MapApp(data_manager)
    window.show()
    sys.exit(app.exec_())