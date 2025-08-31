import sys
import os
from pathlib import Path
import json
from PyQt5.QtCore import QObject, pyqtSlot, QUrl, Qt, QPointF, pyqtSignal, QVariant, pyqtProperty,  QEventLoop
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QFileDialog, QMessageBox, QInputDialog,
                             QSizePolicy, QStatusBar, QSplitter)
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtGui import QIcon, QPixmap
import uuid


class DataManager():
    def __init__(self, data_path):
        self.data_path = data_path
        self.data_file = os.path.join(data_path, "data.json")
        self.current_data = []
        self.ensure_data_file()

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
        """Удаляет точку по ID"""
        self.current_data = [p for p in self.current_data if p.get('id') != point_id]
        self.save_data()

    def clear_all_points(self):
        """Удаляет все точки"""
        self.current_data = []
        self.save_data()



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

        self.btn_clear = QPushButton("Очистить карту")
        self.btn_clear.clicked.connect(self.clear_map)

        for btn in [self.btn_add_point, self.btn_clear]:
            btn.setMinimumHeight(35)
            toolbar_layout.addWidget(btn)

        toolbar_layout.addStretch()
        layout.addWidget(toolbar)

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
        html_content = html_template.replace('/* {{POINTS_DATA}} */', f'var pointsData = {points_json};')

        # Загружаем карту
        self.map_view.setHtml(html_content, QUrl.fromLocalFile(os.path.abspath(".")))

        # Обработчик загрузки карты
        self.map_view.loadFinished.connect(self.on_map_loaded)

    def read_file(self, filename):
        """Читает файл из директории ресурсов"""
        try:
            base_path = Path(__file__).parent
            file_path = os.path.join(base_path, "html_templates", filename)
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"Ошибка чтения файла {filename}: {e}")
            return None

    def on_map_loaded(self):
        """Вызывается после загрузки карты"""
        # Инициализируем точки на карте
        self.map_view.page().runJavaScript("initPoints();")
        self.import_data()

    def enable_add_point_mode(self):
        """Активирует режим добавления точки"""
        self.statusBar().showMessage("Режим добавления: кликните на карту")
        self.point_mode = True
        self.map_view.page().runJavaScript("enableClickHandler();")

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
            "name": data.get("name")
        }

        point_id = self.data_manager.add_point(new_point)
        js_code = f"""
        addMarker(
            {lat}, 
            {lng},
            {json.dumps(new_point['name'])}, 
            '{point_id}'
        );
        """
        self.map_view.page().runJavaScript(js_code)
        self.statusBar().showMessage(f"Добавлена точка: {new_point['name']}")
        self.point_mode = False
        self.dialog_window.close()

    def cancel_point_addition(self):
        if self.point_mode:
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

    def import_data(self):
        """Импортирует данные из файла"""
        file_path = os.path.join(data_dir, "data.json")
        try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    imported_data = json.load(f)

                # Добавляем импортированные данные
                for point in imported_data:
                    self.data_manager.add_point(point)

                # Обновляем карту
                self.map_view.page().runJavaScript("clearMarkers();")
                for point in self.points:
                    js_code = f"addMarker({point['lat']}, {point['lng']}, '{point['name']}', '{point['id']}');"
                    self.map_view.page().runJavaScript(js_code)

                self.statusBar().showMessage(f"Данные импортированы из {file_path}")
        except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось импортировать данные: {str(e)}")



class DialogBridge(QObject):
    formDataSubmitted = pyqtSignal(dict)

    @pyqtSlot(str)
    def sendFormData(self, json_data):
        try:
            data = json.loads(json_data)
            self.formDataSubmitted.emit(data)
        except json.JSONDecodeError as e:
            print(f"Ошибка parsing JSON: {e}")

class DialogWindow(QMainWindow):
    dataSubmitted = pyqtSignal(dict)
    def __init__(self, dataManager, parent=None):
        super().__init__(parent)  # !!! parent
        self.setWindowTitle("Point input window")
        self.resize(500, 500)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)

        # Центральный виджет и компоновка
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        # Создаем карту
        self.form = QWebEngineView()
        self.form.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        layout.addWidget(self.form, 1)
        self.setup_web_channel()
        self.load_temlate()


    def load_temlate(self):
        html_template = self.read_file("form_template.html")

        if not html_template:
            QMessageBox.critical(self, "Ошибка", "Не удалось загрузить шаблон ввода")
            return

        self.form.setHtml(html_template, QUrl("qrc:/"))

    def read_file(self, filename):
        """Читает файл из директории ресурсов"""
        try:
            base_path = Path(__file__).parent
            file_path = os.path.join(base_path, "html_templates", filename)
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
    # Создаем необходимые директории
    base_dir = Path(__file__).parent
    data_dir = os.path.join(base_dir, "data")
    resources_dir = os.path.join(base_dir, "html_templates")

    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(resources_dir, exist_ok=True)

    # Создаем менеджер данных
    data_manager = DataManager(data_dir)

    app = QApplication(sys.argv)
    window = MapApp(data_manager)
    window.show()
    sys.exit(app.exec_())