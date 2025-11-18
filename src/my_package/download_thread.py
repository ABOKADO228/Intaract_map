from PyQt5.QtCore import QThread, pyqtSignal


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
                tiles_downloaded = self.tile_manager.download_visible_area(
                    self.bounds, self.zoom_levels, self.name, self.progress, self
                )
            else:
                tiles_downloaded = self.tile_manager.download_area(
                    self.bounds, self.zoom_levels, self.name, self.progress, self
                )
            self.finished.emit(tiles_downloaded)
        except Exception as exc:
            print(f"Ошибка загрузки: {exc}")
            self.finished.emit(0)
