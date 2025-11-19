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
            file_path = os.path.join(FILE_DIR, fileName)
            if os.path.exists(file_path):
                if sys.platform == "win32":
                    os.startfile(file_path)
                elif sys.platform == "darwin":
                    subprocess.call(("open", file_path))
                else:
                    subprocess.call(("xdg-open", file_path))
                self.parent.statusBar().showMessage(f"Открытие файла: {fileName}")
            else:
                self.parent.statusBar().showMessage(f"Файл не найден: {fileName}")
        except Exception as exc:
            print(f"Ошибка при открытии файла: {exc}")
            self.parent.statusBar().showMessage(f"Ошибка при открытии файла: {fileName}")

    @pyqtSlot(str)
    def openFileLocation(self, fileName):
        try:
            file_path = os.path.join(FILE_DIR, fileName)
            if not os.path.exists(file_path):
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
