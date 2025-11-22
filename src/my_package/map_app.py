import json
import os
import sys
from pathlib import Path

from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtGui import QDoubleValidator
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
from config import BASE_DIR, RESOURCES_DIR
from dialog import DialogWindow
from download_thread import DownloadThread
from tile_manager import TileManager


def _first_existing(paths):
    for path in paths:
        if path.exists():
            return path
    return None


def _runtime_base() -> Path:
    """Корень ресурсов в рантайме (frozen или dev)."""

    return Path(BASE_DIR)


def _configure_webengine_process_path():
    """Установить путь до QtWebEngineProcess, если он был упакован PyInstaller."""

    base_dir = _runtime_base()
    process_name = "QtWebEngineProcess.exe" if os.name == "nt" else "QtWebEngineProcess"
    candidates = [
        base_dir / process_name,
        base_dir / "PyQt5" / "Qt" / "bin" / process_name,
        base_dir / "PyQt5" / "Qt" / "libexec" / process_name,
        base_dir / "PyQt5" / "Qt5" / "bin" / process_name,
        base_dir / "PyQt5" / "Qt5" / "libexec" / process_name,
    ]

    for candidate in candidates:
        if candidate.exists():
            os.environ.setdefault("QTWEBENGINEPROCESS_PATH", str(candidate))
            break


def _frozen_base_candidates() -> list[Path]:
    """Кандидаты базовых путей для упакованного приложения.

    В режиме onedir PyInstaller располагает зависимости рядом с exe или в
    подпапке ``_internal``. В режиме onefile используется ``_MEIPASS``. Чтобы
    покрыть оба варианта, возвращаем список возможных корней для поиска
    ресурсов QtWebEngine.
    """

    candidates: list[Path] = []

    runtime_base = _runtime_base()
    candidates.append(runtime_base)

    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass))

    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        candidates.append(exe_dir)
        candidates.append(exe_dir / "_internal")

    return candidates


def _configure_webengine_resources():
    """Указать Qt путь к ресурсам и локалям WebEngine из упакованной папки."""

    base_candidates = _frozen_base_candidates()

    resource_candidates: list[Path] = []
    locale_candidates: list[Path] = []

    for base_dir in base_candidates:
        resource_candidates.extend(
            [
                base_dir / "resources",
                base_dir / "PyQt5" / "Qt5" / "resources",
                base_dir / "PyQt5" / "Qt" / "resources",
                base_dir / "PyQt6" / "Qt6" / "resources",
                base_dir,
            ]
        )

        locale_candidates.extend(
            [
                base_dir / "resources" / "qtwebengine_locales",
                base_dir / "qtwebengine_locales",
                base_dir / "PyQt5" / "Qt5" / "resources" / "qtwebengine_locales",
                base_dir / "PyQt5" / "Qt" / "resources" / "qtwebengine_locales",
                base_dir / "PyQt5" / "Qt5" / "translations" / "qtwebengine_locales",
                base_dir / "PyQt5" / "Qt" / "translations" / "qtwebengine_locales",
                base_dir / "PyQt6" / "Qt6" / "resources" / "qtwebengine_locales",
                base_dir / "PyQt6" / "Qt6" / "translations" / "qtwebengine_locales",
            ]
        )

    if "QTWEBENGINE_RESOURCES_PATH" not in os.environ:
        resources_dir = _first_existing(
            [path for path in resource_candidates if (path / "qtwebengine_resources.pak").exists()]
        )
        if resources_dir:
            os.environ["QTWEBENGINE_RESOURCES_PATH"] = str(resources_dir)

    if "QTWEBENGINE_LOCALES_PATH" not in os.environ:
        locales_dir = _first_existing(
            [path for path in locale_candidates if path.exists() and any(path.glob("*.pak"))]
        )
        if locales_dir:
            os.environ["QTWEBENGINE_LOCALES_PATH"] = str(locales_dir)


_configure_webengine_process_path()
_configure_webengine_resources()


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
        self.point_dialog_was_saved = False

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
        self.btn_add_point_by_coords = QPushButton("Добавить по координатам")
        self.btn_add_point_by_coords.clicked.connect(self.prompt_coordinates)
        self.btn_del_point = QPushButton("Удалить выбранные точки")
        self.btn_del_point.clicked.connect(self.remove_selected_points)
        self.btn_edit_point = QPushButton("Изменить выбранную точку")
        self.btn_edit_point.clicked.connect(self.request_point_edit)

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
            self.btn_add_point_by_coords,
            self.btn_del_point,
            self.btn_edit_point,
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

    def request_point_edit(self):
        script = """
            (function() {
                if (typeof getSelectedMarkerIds === 'function') {
                    return JSON.stringify(getSelectedMarkerIds());
                }
                return '[]';
            })();
        """

        def handle_selection(result):
            try:
                selection = json.loads(result) if result else []
            except json.JSONDecodeError:
                selection = []

            if not selection:
                QMessageBox.information(self, "Редактирование", "Выберите точку для изменения")
                return

            if len(selection) > 1:
                QMessageBox.information(
                    self, "Редактирование", "Выберите только одну точку для изменения"
                )
                return

            self.edit_point(selection[0])

        self.map_view.page().runJavaScript(script, handle_selection)

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

            base_url = QUrl.fromLocalFile(str(Path(RESOURCES_DIR).resolve()) + "/")
            self.map_view.setHtml(html_content, base_url)
            self.map_view.loadFinished.connect(self.on_map_loaded)

        except Exception as exc:
            print(f"Ошибка загрузки карты: {exc}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить карту: {exc}")

    def read_file(self, filename):
        try:
            file_path = Path(RESOURCES_DIR) / filename
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
            if (typeof window.ensureWebChannel === 'function') {
                window.ensureWebChannel();
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

        self._open_point_dialog(lat, lng, via_map_click=True)

    def edit_point(self, point_id):
        point = next((p for p in self.points if p.get("id") == point_id), None)
        if not point:
            QMessageBox.warning(self, "Редактирование", "Точка не найдена")
            return

        self.edit_dialog = DialogWindow(self, point)
        self.edit_dialog.dataSubmitted.connect(
            lambda data, pid=point_id: self.process_point_edit(pid, data)
        )
        self.edit_dialog.show()

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
        self.point_dialog_was_saved = True
        if self.point_mode:
            self.map_view.page().runJavaScript("disableClickHandler();")
            self.point_mode = False
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
        self.points = self.data_manager.current_data
        self.dialog_window.close()

    def focus_map_on(self, lat, lng):
        js_code = f"focusOnCoordinates({lat}, {lng});"
        self.map_view.page().runJavaScript(js_code)

    def _open_point_dialog(self, lat, lng, via_map_click=False):
        self.point_dialog_was_saved = False
        self.dialog_window = DialogWindow(self)
        self.dialog_window.dataSubmitted.connect(
            lambda data: self.process_point_data(lat, lng, data)
        )

        self.dialog_window.destroyed.connect(
            lambda: self.on_point_dialog_closed(via_map_click)
        )

        self.dialog_window.show()
        self.focus_map_on(lat, lng)

    def on_point_dialog_closed(self, via_map_click: bool):
        if getattr(self, "point_dialog_was_saved", False):
            return

        if via_map_click:
            self.cancel_point_addition()
        else:
            self.statusBar().showMessage("Форма добавления закрыта")

    def process_point_edit(self, point_id, data):
        point = next((p for p in self.points if p.get("id") == point_id), None)
        if not point:
            QMessageBox.warning(self, "Редактирование", "Точка не найдена")
            return

        combined_files = (
            (data.get("existingFileNames") or point.get("fileNames") or [])
            + data.get("fileNames", [])
        )

        updated_point = {
            **point,
            "name": data.get("name", point.get("name")),
            "deep": data.get("deep", point.get("deep")),
            "filters": data.get("filters", point.get("filters")),
            "debit": data.get("debit", point.get("debit")),
            "comments": data.get("comments", point.get("comments")),
            "color": data.get("color", point.get("color", "#4361ee")),
            "fileNames": combined_files,
        }
        updated_point["fileName"] = (
            updated_point.get("fileNames", [""])[0] if updated_point.get("fileNames") else ""
        )

        if self.data_manager.update_point(point_id, updated_point):
            self.points = self.data_manager.current_data

            js_code = f"updateMarkerData({json.dumps(updated_point, ensure_ascii=False)});"
            self.map_view.page().runJavaScript(js_code)
            self.statusBar().showMessage(
                f"Данные точки '{updated_point.get('name')}' обновлены"
            )
            if hasattr(self, "edit_dialog"):
                self.edit_dialog.close()
        else:
            QMessageBox.warning(self, "Редактирование", "Не удалось обновить точку")

    def cancel_point_addition(self):
        self.statusBar().showMessage("Добавление точки отменено")
        self.point_mode = False
        self.map_view.page().runJavaScript("disableClickHandler();")

    def prompt_coordinates(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Добавить точку по координатам")
        dialog.setFixedSize(360, 220)

        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Введите широту и долготу точки:"))

        lat_input = QLineEdit()
        lat_input.setPlaceholderText("Широта, например 59.9386")
        lat_input.setValidator(QDoubleValidator(-90.0, 90.0, 8, lat_input))

        lng_input = QLineEdit()
        lng_input.setPlaceholderText("Долгота, например 30.3141")
        lng_input.setValidator(QDoubleValidator(-180.0, 180.0, 8, lng_input))

        coords_layout = QGridLayout()
        coords_layout.addWidget(QLabel("Широта"), 0, 0)
        coords_layout.addWidget(lat_input, 0, 1)
        coords_layout.addWidget(QLabel("Долгота"), 1, 0)
        coords_layout.addWidget(lng_input, 1, 1)

        layout.addLayout(coords_layout)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(buttons)

        def handle_accept():
            lat_text = lat_input.text().replace(",", ".").strip()
            lng_text = lng_input.text().replace(",", ".").strip()

            try:
                lat_value = float(lat_text)
                lng_value = float(lng_text)
            except ValueError:
                QMessageBox.warning(self, "Неверные данные", "Введите корректные числовые координаты")
                return

            if not (-90.0 <= lat_value <= 90.0 and -180.0 <= lng_value <= 180.0):
                QMessageBox.warning(
                    self,
                    "Неверные координаты",
                    "Широта должна быть в диапазоне [-90; 90], долгота — [-180; 180]",
                )
                return

            dialog.accept()
            self.statusBar().showMessage(
                f"Добавление точки по координатам: {lat_value:.6f}, {lng_value:.6f}"
            )
            self._open_point_dialog(lat_value, lng_value)

        buttons.accepted.connect(handle_accept)
        buttons.rejected.connect(dialog.reject)

        dialog.exec_()

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
