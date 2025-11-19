import json
import os
import subprocess
import sys

from PyQt5.QtCore import QObject, pyqtSlot

from config import FILE_DIR


class Bridge(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent

    def _resolve_file_path(self, file_name: str) -> str:
        """Return an existing file path for the stored attachment name."""

        if not file_name:
            return ""

        candidates = []

        # Allow absolute paths that already exist (legacy records)
        if os.path.isabs(file_name):
            candidates.append(file_name)

        # Support relative entries that may already include subdirectories
        candidates.append(os.path.abspath(file_name))

        # Default location for stored attachments
        candidates.append(os.path.join(FILE_DIR, file_name))

        for candidate in candidates:
            if candidate and os.path.exists(candidate):
                return os.path.normpath(candidate)

        return ""

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
        except json.JSONDecodeError as exc:
            print(f"Ошибка parsing JSON: {exc}")

    @pyqtSlot(str)
    def openFileInWord(self, fileName):
        try:
            file_path = self._resolve_file_path(fileName)
            if file_path:
                if sys.platform == "win32":
                    os.startfile(file_path)
                elif sys.platform == "darwin":
                    subprocess.call(("open", file_path))
                else:
                    subprocess.call(("xdg-open", file_path))

                self.parent.statusBar().showMessage(
                    f"Открытие файла: {os.path.basename(file_path)}"
                )
            else:
                self.parent.statusBar().showMessage(
                    f"Файл не найден: {fileName}"
                )
        except Exception as exc:
            print(f"Ошибка при открытии файла: {exc}")
            self.parent.statusBar().showMessage(f"Ошибка при открытии файла: {fileName}")

    @pyqtSlot(str)
    def openFileLocation(self, fileName):
        try:
            file_path = self._resolve_file_path(fileName)
            if not file_path:
                self.parent.statusBar().showMessage(f"Файл не найден: {fileName}")
                return

            target_dir = os.path.dirname(file_path) or FILE_DIR

            if sys.platform == "win32":
                subprocess.Popen(["explorer", "/select,", file_path])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-R", file_path])
            else:
                subprocess.Popen(["xdg-open", target_dir])

            self.parent.statusBar().showMessage(
                f"Открытие каталога для файла: {fileName}"
            )
        except Exception as exc:
            print(f"Ошибка при открытии каталога файла: {exc}")
            self.parent.statusBar().showMessage(
                f"Ошибка при открытии каталога для файла: {fileName}"
            )

    @pyqtSlot(str, result=str)
    def getTile(self, url):
        try:
            result = self.parent.tile_manager.get_tile_data_url(url)
            return result or ""
        except Exception as exc:
            print(f"Ошибка в getTile: {exc}")
            return ""

    @pyqtSlot(result=str)
    def getOfflineStats(self):
        try:
            stats = self.parent.tile_manager.get_stats()
            return json.dumps(stats)
        except Exception as exc:
            print(f"Ошибка в getOfflineStats: {exc}")
            return json.dumps({"error": str(exc)})

    @pyqtSlot()
    def switchToOfflineMode(self):
        self.parent.force_offline_mode()

    @pyqtSlot()
    def switchToOnlineMode(self):
        self.parent.force_online_mode()

    @pyqtSlot(result=str)
    def getCurrentMapBounds(self):
        try:
            bounds = self.parent.get_current_map_bounds()
            return json.dumps(bounds) if bounds else "null"
        except Exception as exc:
            print(f"Ошибка получения границ карты: {exc}")
            return "null"

    @pyqtSlot(result=int)
    def getCurrentZoom(self):
        try:
            return self.parent.get_current_zoom()
        except Exception as exc:
            print(f"Ошибка получения zoom уровня: {exc}")
            return 12
