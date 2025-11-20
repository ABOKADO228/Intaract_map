import json
import os
import sys
from pathlib import Path

from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QSpinBox,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from bridge import Bridge
from config import RESOURCES_DIR
from dialog import DialogWindow
from download_thread import DownloadThread
from tile_manager import TileManager


def _configure_webengine_process_path():
    """Установить путь до QtWebEngineProcess, если он был упакован PyInstaller."""

    base_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    process_name = "QtWebEngineProcess.exe" if os.name == "nt" else "QtWebEngineProcess"
    candidates = [
        base_dir / process_name,
        base_dir / "PyQt5" / "Qt" / "bin" / process_name,
        base_dir / "PyQt5" / "Qt" / "libexec" / process_name,
    ]

    for candidate in candidates:
        if candidate.exists():
            os.environ.setdefault("QTWEBENGINEPROCESS_PATH", str(candidate))
            break


_configure_webengine_process_path()


class MapApp(QMainWindow):
    def __init__(self, data_manager):
        super().__init__()
        self.data_manager = data_manager
        self.points = data_manager.current_data
        self.point_mode = False
        self.tile_manager = TileManager(data_manager.data_path)
        self.download_thread = None
        self.current_mode = "offline"
        self.current_bounds = None
        self.current_zoom = 12

        self.setup_ui()
        self.setup_web_channel()
        self.load_map_html()

    def setup_ui(self):
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
        self.setup_toolbar(layout)

    def center_window(self):
        frame_geometry = self.frameGeometry()
        center_point = QApplication.primaryScreen().availableGeometry().center()
        frame_geometry.moveCenter(center_point)
        self.move(frame_geometry.topLeft())

    def setup_toolbar(self, layout):
        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)

        self.btn_add_point = QPushButton("Добавить точку")
        self.btn_add_point.clicked.connect(self.enable_add_point_mode)
        self.btn_del_point = QPushButton("Удалить выбранные точки")
        self.btn_del_point.clicked.connect(self.remove_selected_points)

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
            self.btn_clear_cache,
        ]

        for btn in buttons:
            btn.setMinimumHeight(35)
            btn.setMinimumWidth(160)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(
                """
QPushButton {
    padding: 8px 12px;
    background: #4361ee;
    color: white;
    border: none;
    border-radius: 6px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #2980b9;
}
QPushButton:pressed {
    background-color: #1c6ea4;
}
"""
            )
            toolbar_layout.addWidget(btn)

        toolbar_layout.addStretch()
        layout.addWidget(toolbar)

    def remove_selected_points(self):
        self.map_view.page().runJavaScript("removeSelectedPoints();")

    def setup_web_channel(self):
        self.bridge = Bridge(self)
        self.channel = QWebChannel()
        self.channel.registerObject("bridge", self.bridge)
        self.map_view.page().setWebChannel(self.channel)
        self.map_view.loadFinished.connect(self._ensure_js_channel)

    def load_map_html(self):
        try:
            html_template = self.read_file("map_template.html")
            if not html_template:
                QMessageBox.critical(self, "Ошибка", "Не удалось загрузить шаблон карты")
                return

            points_json = json.dumps(self.points, ensure_ascii=False)
            html_content = html_template.replace(
                "/* {{POINTS_DATA}} */", f"var initialMarkerData = {points_json};"
            )

            base_url = QUrl.fromLocalFile(str(RESOURCES_DIR) + "/")
            self.map_view.setHtml(html_content, base_url)
            self.map_view.loadFinished.connect(self.on_map_loaded)

        except Exception as exc:
            print(f"Ошибка загрузки карты: {exc}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить карту: {exc}")

    def read_file(self, filename):
        try:
            file_path = os.path.join(RESOURCES_DIR, filename)
            with open(file_path, "r", encoding="utf-8") as handle:
                return handle.read()
        except Exception as exc:
            print(f"Ошибка чтения файла {filename}: {exc}")
            return None

    def on_map_loaded(self):
        self.map_view.page().runJavaScript("initPoints();")

    def _ensure_js_channel(self):
        """Guarantee the JS side sees the registered bridge after each load."""

        script = """
            if (typeof qt !== 'undefined' && qt.webChannelTransport) {
                new QWebChannel(qt.webChannelTransport, function(channel) {
                    if (typeof window.setBridge === 'function') {
                        window.setBridge(channel.objects.bridge);
                    } else {
                        window.bridge = channel.objects.bridge;
                    }
                    if (typeof window.onBridgeReady === 'function') {
                        window.onBridgeReady();
                    }
                });
            }
        """
        self.map_view.page().runJavaScript(script)

    def get_current_map_bounds(self):
        return self.current_bounds

    def get_current_zoom(self):
        return self.current_zoom

    def enable_add_point_mode(self):
        if not self.point_mode:
            self.statusBar().showMessage("Режим добавления: кликните на карту")
            self.point_mode = True
            self.map_view.page().runJavaScript("enableClickHandler();")
            self.btn_add_point.setStyleSheet(
                """
                QPushButton {
                    padding: 8px 12px;
                    background: #1c6ea4;
                    color: white;
                    border: none;
                    border-radius: 6px;
                    font-weight: bold;
                    width: 100%;
                }
                QPushButton:hover {
                    background-color: #2980b9;
                }
                QPushButton:pressed {
                    background-color: #1c6ea4;
                }
            """
            )
        else:
            self.statusBar().showMessage("Отмена режима добавления точки")
            self.point_mode = False
            self.map_view.page().runJavaScript("disableClickHandler();")
            self.btn_add_point.setStyleSheet(
                """
                QPushButton {
                    padding: 8px 12px;
                    background: #4361ee;
                    color: white;
                    border: none;
                    border-radius: 6px;
                    font-weight: bold;
                    width: 100%;
                }
                QPushButton:hover {
                    background-color: #2980b9;
                }
                QPushButton:pressed {
                    background-color: #1c6ea4;
                }
            """
            )

    def add_point(self, lat, lng):
        if not self.point_mode:
            return

        self.dialog_window = DialogWindow(self)
        self.dialog_window.dataSubmitted.connect(
            lambda data: self.process_point_data(lat, lng, data)
        )
        self.dialog_window.destroyed.connect(lambda: self.cancel_point_addition())
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
            "fileName": data.get("fileNames", [""])[0] if data.get("fileNames") else "",
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
        self.statusBar().showMessage(
            f"Добавлена точка: {new_point['name']} с {len(new_point['fileNames'])} файлами"
        )
        self.map_view.page().runJavaScript("disableClickHandler();")
        self.points = self.data_manager.current_data
        self.dialog_window.close()
        self.point_mode = False

    def cancel_point_addition(self):
        self.statusBar().showMessage("Добавление точки отменено")
        self.point_mode = False
        self.map_view.page().runJavaScript("disableClickHandler();")

    def remove_point(self, point_id):
        point = next((p for p in self.points if p.get("id") == point_id), None)
        if point:
            file_count = len(point.get("fileNames", []))
            file_text = f" с {file_count} файлами" if file_count > 0 else ""

            first_reply = QMessageBox.question(
                self,
                "Подтверждение",
                f"Вы действительно хотите удалить точку '{point['name']}'{file_text}?",
                QMessageBox.Yes | QMessageBox.No,
            )

            if first_reply != QMessageBox.Yes:
                return

            second_reply = QMessageBox.question(
                self,
                "Подтверждение удаления",
                "Это действие необратимо. Удалить точку окончательно?",
                QMessageBox.Yes | QMessageBox.No,
            )

            if second_reply == QMessageBox.Yes:
                self.data_manager.remove_point(point_id)
                self.map_view.page().runJavaScript(f"removeMarker('{point_id}');")
                self.statusBar().showMessage(f"Точка '{point['name']}' удалена")

    def clear_map(self):
        reply = QMessageBox.question(
            self,
            "Подтверждение",
            "Вы действительно хотите очистить карту и удалить все точки?",
            QMessageBox.Yes | QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            self.data_manager.clear_all_points()
            self.map_view.page().runJavaScript("clearMarkers();")
            self.statusBar().showMessage("Все точки удалены")
            self.point_mode = False

    def update_color(self, points_data):
        try:
            points_dict = {point["id"]: point for point in self.data_manager.current_data}

            for point in points_data:
                if point["id"] in points_dict:
                    points_dict[point["id"]]["color"] = point.get("color", "#4361ee")

            self.data_manager.current_data = list(points_dict.values())
            self.data_manager.save_data()
            self.points = self.data_manager.current_data

            self.statusBar().showMessage("Цвета маркеров успешно обновлены")
        except Exception as exc:
            print(f"Ошибка при обновлении цветов: {exc}")
            self.statusBar().showMessage("Ошибка при обновлении цветов маркеров")

    def download_offline_map(self):
        if self.points:
            lats = [p["lat"] for p in self.points]
            lngs = [p["lng"] for p in self.points]
            bounds = [min(lats), min(lngs), max(lats), max(lngs)]
        else:
            bounds = [59.8, 30.1, 60.1, 30.5]

        self.show_download_dialog(bounds, "CartoDB Voyager - Моя офлайн карта")

    def download_visible_area(self):
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
                    bounds_data["south"],
                    bounds_data["west"],
                    bounds_data["north"],
                    bounds_data["east"],
                ]
                current_zoom = bounds_data["zoom"]
                self.show_visible_area_dialog(bounds, current_zoom)

            except Exception as exc:
                print(f"Ошибка получения границ карты: {exc}")
                QMessageBox.warning(self, "Ошибка", "Не удалось получить границы карты")

        self.map_view.page().runJavaScript(js_code, handle_bounds)

    def show_visible_area_dialog(self, bounds, current_zoom):
        dialog = QDialog(self)
        dialog.setWindowTitle("Скачать видимую область CartoDB Voyager")
        dialog.setFixedSize(500, 450)
        layout = QVBoxLayout(dialog)

        info_group = QGroupBox("Информация о видимой области")
        info_layout = QGridLayout(info_group)

        info_layout.addWidget(QLabel("Текущий zoom:"), 0, 0)
        info_layout.addWidget(QLabel(f"{current_zoom}"), 0, 1)

        info_layout.addWidget(QLabel("Границы:"), 1, 0)
        bounds_label = QLabel(
            f"{bounds[0]:.4f}, {bounds[1]:.4f}, {bounds[2]:.4f}, {bounds[3]:.4f}"
        )
        bounds_label.setWordWrap(True)
        info_layout.addWidget(bounds_label, 1, 1)

        layout.addWidget(info_group)

        zoom_group = QGroupBox("Выбор zoom слоев для скачивания")
        zoom_layout = QGridLayout(zoom_group)

        zoom_layout.addWidget(QLabel("Минимальный zoom:"), 0, 0)
        min_zoom = QSpinBox()
        min_zoom.setRange(0, 18)
        min_zoom.setValue(max(0, current_zoom - 2))
        zoom_layout.addWidget(min_zoom, 0, 1)

        zoom_layout.addWidget(QLabel("Максимальный zoom:"), 1, 0)
        max_zoom = QSpinBox()
        max_zoom.setRange(0, 18)
        max_zoom.setValue(min(18, current_zoom + 2))
        zoom_layout.addWidget(max_zoom, 1, 1)

        zoom_layout.addWidget(QLabel("Количество слоев:"), 2, 0)
        zoom_count_label = QLabel(f"{max_zoom.value() - min_zoom.value() + 1}")
        zoom_layout.addWidget(zoom_count_label, 2, 1)

        zoom_layout.addWidget(QLabel("Выбранные zoom:"), 3, 0)
        zoom_list_label = QLabel(self.get_zoom_list_text(min_zoom.value(), max_zoom.value()))
        zoom_list_label.setWordWrap(True)
        zoom_layout.addWidget(zoom_list_label, 3, 1)

        layout.addWidget(zoom_group)

        layout.addWidget(QLabel("Название области:"))
        name_input = QLineEdit(
            f"CartoDB Voyager - Видимая область (zoom {min_zoom.value()}-{max_zoom.value()})"
        )
        layout.addWidget(name_input)

        estimated_size = self.tile_manager.estimate_download_size(
            bounds, list(range(min_zoom.value(), max_zoom.value() + 1))
        )
        size_label = QLabel(f"Примерный размер: {estimated_size} МБ")
        layout.addWidget(size_label)

        def update_size():
            zoom_levels = list(range(min_zoom.value(), max_zoom.value() + 1))
            estimated = self.tile_manager.estimate_download_size(bounds, zoom_levels)
            size_label.setText(f"Примерный размер: {estimated} МБ")
            zoom_count_label.setText(f"{len(zoom_levels)}")
            zoom_list_label.setText(self.get_zoom_list_text(min_zoom.value(), max_zoom.value()))
            name_input.setText(
                f"CartoDB Voyager - Видимая область (zoom {min_zoom.value()}-{max_zoom.value()})"
            )

        min_zoom.valueChanged.connect(update_size)
        max_zoom.valueChanged.connect(update_size)

        info_label = QLabel(
            "Будут загружены тайлы для выбранных zoom уровней в пределах видимой области."
        )
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
        if min_zoom.value() > max_zoom.value():
            max_zoom.setValue(min_zoom.value())

    def get_zoom_list_text(self, min_zoom, max_zoom):
        if max_zoom - min_zoom <= 5:
            return ", ".join(map(str, range(min_zoom, max_zoom + 1)))
        return f"{min_zoom}-{max_zoom}"

    def show_download_dialog(self, bounds, default_name):
        dialog = QDialog(self)
        dialog.setWindowTitle("Скачать офлайн-карту CartoDB Voyager")
        dialog.setFixedSize(400, 350)
        layout = QVBoxLayout(dialog)

        layout.addWidget(QLabel("Область карты:"))
        bounds_label = QLabel(
            f"Границы: {bounds[0]:.4f}, {bounds[1]:.4f}, {bounds[2]:.4f}, {bounds[3]:.4f}"
        )
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

        estimated_size = self.tile_manager.estimate_download_size(
            bounds, list(range(min_zoom.value(), max_zoom.value() + 1))
        )
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
        progress_dialog = QDialog(self)
        if is_visible_area:
            progress_dialog.setWindowTitle("Загрузка видимой области CartoDB Voyager")
        else:
            progress_dialog.setWindowTitle("Загрузка офлайн-карты CartoDB Voyager")

        progress_dialog.setFixedSize(400, 150)
        progress_layout = QVBoxLayout(progress_dialog)

        if is_visible_area:
            progress_label = QLabel(
                f"Загрузка видимой области ({len(zoom_levels)} zoom слоев)..."
            )
        else:
            progress_label = QLabel(
                f"Загрузка тайлов CartoDB Voyager ({len(zoom_levels)} zoom слоев)..."
            )
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
            lambda current, total: self.on_download_progress(
                current, total, progress_bar, progress_text
            )
        )
        self.download_thread.finished.connect(
            lambda count: self.on_download_finished(
                count, progress_dialog, is_visible_area, zoom_levels
            )
        )
        self.download_thread.start()

    def cancel_download(self, progress_dialog):
        if self.download_thread and self.download_thread.isRunning():
            self.download_thread.stop()
            self.download_thread.wait(1000)
        progress_dialog.close()
        self.statusBar().showMessage("Загрузка отменена")

    def on_download_progress(self, current, total, progress_bar, progress_label):
        if total > 0:
            progress = int((current / total) * 100)
            progress_bar.setValue(progress)
            progress_label.setText(f"Загружено: {current} из {total} тайлов ({progress}%)")

    def on_download_finished(self, tiles_downloaded, progress_dialog, is_visible_area, zoom_levels):
        progress_dialog.close()

        if tiles_downloaded > 0:
            if is_visible_area:
                message = (
                    f"Загружено {tiles_downloaded} тайлов видимой области "
                    f"({len(zoom_levels)} zoom слоев)"
                )
            else:
                message = (
                    f"Загружено {tiles_downloaded} тайлов CartoDB Voyager "
                    f"({len(zoom_levels)} zoom слоев)"
                )

            QMessageBox.information(self, "Загрузка завершена", message)
            self.statusBar().showMessage(message)
        else:
            QMessageBox.information(
                self,
                "Загрузка завершена",
                "Все тайлы уже загружены в кэш",
            )

    def show_offline_stats(self):
        stats = self.tile_manager.get_stats()

        stats_text = """
        CartoDB Voyager - Офлайн карты:
        Всего тайлов: {total_tiles}
        Областей: {tileset_count}
        Размер кэша: {total_size} MB

        Доступные области:
        """.format(
            total_tiles=stats["total_tiles"],
            tileset_count=len(stats["tilesets"]),
            total_size=stats["total_size_mb"],
        )

        for name, info in stats["tilesets"].items():
            stats_text += f"\n- {name}: zoom {info['min_zoom']}-{info['max_zoom']}"

        if not stats["tilesets"]:
            stats_text += "\nНет сохраненных областей"

        QMessageBox.information(self, "Статистика офлайн-карт CartoDB Voyager", stats_text)

    def clear_offline_cache(self):
        reply = QMessageBox.question(
            self,
            "Подтверждение",
            "Вы действительно хотите очистить кэш офлайн-карт CartoDB Voyager?\n"
            "Все скачанные тайлы будут удалены.",
            QMessageBox.Yes | QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            if self.tile_manager.clear_cache():
                QMessageBox.information(
                    self, "Успех", "Кэш офлайн-карт CartoDB Voyager очищен"
                )
                self.statusBar().showMessage("Кэш офлайн-карт CartoDB Voyager очищен")
            else:
                QMessageBox.warning(self, "Ошибка", "Не удалось очистить кэш")

    def force_offline_mode(self):
        self.current_mode = "offline"
        self.map_view.page().runJavaScript("switchToOfflineLayer();")
        self.statusBar().showMessage("CartoDB Voyager - Офлайн режим активирован")

    def force_online_mode(self):
        self.current_mode = "online"
        self.map_view.page().runJavaScript("switchToOnlineLayer();")
        self.statusBar().showMessage("CartoDB Voyager - Онлайн режим активирован")
