import sys

from PyQt5.QtWidgets import QApplication

from .data_manager import DataManager
from .map_app import MapApp
from .paths import DATA_DIR


def main():
    data_manager = DataManager(DATA_DIR)
    app = QApplication(sys.argv)
    window = MapApp(data_manager)
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
