import sys
import os
from pathlib import Path
import json
from PyQt5.QtCore import QObject, pyqtSlot, QUrl, Qt
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QFileDialog, QMessageBox, QInputDialog,
                             QSizePolicy, QStatusBar)
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtGui import QIcon, QPixmap


class Data():
    def __init__(self):
        self.dataFileName = os.path.join(data_path, "data.json")
        self.currentData = []

        # Создаем файл, если он не существует
        if not os.path.exists(self.dataFileName):
            with open(self.dataFileName, "w", encoding="utf-8") as file:
                json.dump(self.currentData, file, ensure_ascii=False, indent=4)
        else:
            self.read_data()

    def read_data(self):
        try:
            with open(self.dataFileName, 'r', encoding='utf-8') as file:
                self.currentData = json.load(file)
        except (json.JSONDecodeError, FileNotFoundError):
            self.currentData = []

    def write_data(self, data):
        self.read_data()  # Всегда читаем актуальные данные
        self.currentData.append(data)
        with open(self.dataFileName, "w", encoding="utf-8") as file:
            json.dump(self.currentData, file, ensure_ascii=False, indent=4)


class Bridge(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent

    @pyqtSlot(float, float)
    def addPoint(self, lat, lng):
        self.parent.add_point(lat, lng)


class MapApp(QMainWindow):
    def __init__(self, data):
        super().__init__()

        # Сохраняем ссылку на объект данных
        self.data = data

        # Текущие точки
        self.points = data.currentData

        self.setWindowTitle("Картографическое приложение")
        screen_geometry = QApplication.desktop().screenGeometry()
        x = (screen_geometry.width() - 1200) // 2
        y = (screen_geometry.height() - 800) // 2
        self.setGeometry(x, y, 1200, 800)

        # Основной виджет
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        # Создаем карту
        self.create_map_widget()

        # Панель инструментов
        self.create_toolbar()

        # Статус бар
        self.statusBar().showMessage("Готово")

        self.point_mode = False

    def create_map_widget(self):
        """Создаем виджет карты"""
        self.map_view = QWebEngineView()
        self.map_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Создаем и загружаем HTML карты
        self.load_map_html()

        self.layout.addWidget(self.map_view, 1)

        # Откладываем отрисовку точек до полной загрузки карты
        self.map_view.loadFinished.connect(self.on_map_loaded)

    def on_map_loaded(self):
        """Вызывается после загрузки карты"""
        self.plot_points_on_map()

    def load_map_html(self):
        """Загружаем HTML-карту"""
        html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>Интерактивная карта</title>
    <meta charset="utf-8">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.7.1/dist/leaflet.css"/>
    <style>
        #map {
            width: 100%;
            height: 100vh;
        }
        body, html {
            margin: 0;
            padding: 0;
            height: 100%;
    }
    </style>
</head>
<body>
    <div id="map"></div>

    <script src="https://unpkg.com/leaflet@1.7.1/dist/leaflet.js"></script>
    <!-- Важно: добавляем скрипт qwebchannel.js -->
    <script type="text/javascript" src="qrc:///qtwebchannel/qwebchannel.js"></script>

    <script>
        // Инициализация карты
        var map = L.map('map').setView([55.7558, 37.6173], 12); // Москва по умолчанию

        var markers = L.layerGroup().addTo(map);
        var bridge = null; // Объект для связи с Python

        // Инициализация WebChannel после загрузки страницы
        document.addEventListener("DOMContentLoaded", function() {
            // Проверяем, доступен ли WebChannel
            if (typeof qt !== 'undefined') {
                new QWebChannel(qt.webChannelTransport, function(channel) {
                    bridge = channel.objects.bridge;
                    console.log("WebChannel инициализирован");
                });
            } else {
                console.error("WebChannel не доступен");
            }
        });

        // Добавление слоя OpenStreetMap
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        }).addTo(map);

        // Добавление маркера
        function addMarker(lat, lng, name) {
            var marker = L.marker([lat, lng]);
            if (name) {
                marker.addTo(markers);
                marker.bindPopup(name).openPopup();
            }
            return marker;
        }

        // Очистка всех маркеров
        function clearMarkers() {
            markers.clearLayers();
        }

        // Включение обработчика кликов
        function enableClickHandler() {
            map.on('click', function(e) {
                console.log("Клик на карте: ", e.latlng);
                // Передаем координаты в приложение
                if (bridge) {
                    bridge.addPoint(e.latlng.lat, e.latlng.lng);
                } else {
                    console.error("Объект bridge не инициализирован");
                }
            });
            console.log("Обработчик кликов активирован");
        }

        // Отключение обработчика кликов
        function disableClickHandler() {
            map.off('click');
            console.log("Обработчик кликов деактивирован");
        }
    </script>
</body>
</html>
        """

        # Создаем временный файл
        map_file = os.path.join(temp_path, "map_temp.html")
        with open(map_file, "w", encoding="utf-8") as f:
            f.write(html_content)

        # Загружаем карту
        self.map_view.load(QUrl.fromLocalFile(map_file))

        # Настраиваем связь с JavaScript
        self.bridge = Bridge(self)
        self.channel = QWebChannel()
        self.channel.registerObject('bridge', self.bridge)
        self.map_view.page().setWebChannel(self.channel)

    def create_toolbar(self):
        """Создаем панель инструментов"""
        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)

        self.btn_add_point = QPushButton("Добавить точку")
        self.btn_add_point.setMinimumHeight(40)
        self.btn_add_point.clicked.connect(self.enable_add_point_mode)

        self.btn_clear = QPushButton("Очистить карту")
        self.btn_clear.setMinimumHeight(40)
        self.btn_clear.clicked.connect(self.clear_map)

        # Добавляем элементы на панель
        toolbar_layout.addWidget(self.btn_add_point)
        toolbar_layout.addWidget(self.btn_clear)

        self.layout.addWidget(toolbar)

    def plot_points_on_map(self):
        """Отображение точек на карте"""
        # Добавляем новые точки
        for point in self.points:
            self.load_point(point.get("lat"), point.get("lng"), point.get("name"))

    def enable_add_point_mode(self):
        """Активируем режим добавления точки"""
        self.statusBar().showMessage("Режим добавления: кликните на карту")
        self.point_mode = True
        self.map_view.page().runJavaScript("enableClickHandler();")

    def add_point(self, lat, lng):
        """Добавление новой точки (вызывается из JavaScript)"""
        if not self.point_mode:
            return

        self.point_mode = False
        point_name, ok = QInputDialog.getText(
            self, "Название точки", "Введите название точки:"
        )

        if ok and point_name:
            new_point = {
                "lat": lat,
                "lng": lng,
                "name": point_name
            }
            self.points.append(new_point)

            # Добавляем маркер на карту
            js_code = f"addMarker({lat}, {lng}, `{point_name}`);"
            self.map_view.page().runJavaScript(js_code)

            self.statusBar().showMessage(f"Добавлена точка: {point_name}")

            # Используем сохраненную ссылку на объект данных
            self.data.write_data(new_point)

        # Отключаем обработчик кликов
        self.map_view.page().runJavaScript("disableClickHandler();")

    def load_point(self, lat, lng, point_name):
        # Добавляем маркер на карту
        js_code = f"addMarker({lat}, {lng}, `{point_name}`);"
        self.map_view.page().runJavaScript(js_code)

    def clear_map(self):
        """Очистка карты и списка точек"""
        reply = QMessageBox.question(
            self, "Подтверждение",
            "Вы действительно хотите очистить карту?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.map_view.page().runJavaScript("clearMarkers();")
            self.statusBar().showMessage("Карта очищена")
            self.point_mode = False


if __name__ == "__main__":
    current_dir = Path(__file__).parent
    data_path = os.path.join(current_dir, "data")
    temp_path = os.path.join(current_dir, "html_templates")
    # Создаем объект данных первым
    data = Data()

    app = QApplication(sys.argv)
    # Передаем объект данных в конструктор MapApp
    window = MapApp(data)
    window.show()
    sys.exit(app.exec_())