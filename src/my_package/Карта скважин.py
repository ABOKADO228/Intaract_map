import logging
import os
import sys


def set_qt_plugin_path():
    if getattr(sys, "frozen", False):
        base_path = sys._MEIPASS
        qt_plugin_path = os.path.join(base_path, "qt5_plugins").replace("\\", "/")
        os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = qt_plugin_path

        webengine_process_path = os.path.join(base_path, "bin", "QtWebEngineProcess.exe").replace("\\", "/")
        os.environ["QTWEBENGINEPROCESS_PATH"] = webengine_process_path


def setup_qt_paths():
    if getattr(sys, "frozen", False):
        base_path = sys._MEIPASS

        qt_paths = [
            os.path.join(base_path, "bin"),
            os.path.join(base_path, "plugins"),
            os.path.join(base_path, "resources"),
        ]

        for path in qt_paths:
            if os.path.exists(path) and path not in os.environ["PATH"]:
                os.environ["PATH"] = path + os.pathsep + os.environ["PATH"]

        webengine_process = os.path.join(base_path, "QtWebEngineProcess.exe")
        if os.path.exists(webengine_process):
            os.environ["QTWEBENGINEPROCESS_PATH"] = webengine_process

        os.environ["QTWEBENGINE_RESOURCES_PATH"] = os.path.join(base_path, "resources")


def debug_qt_paths():
    print("=== QT DEBUG INFO ===")
    print("Frozen:", getattr(sys, "frozen", False))

    if getattr(sys, "frozen", False):
        base_path = sys._MEIPASS
        print("MEIPASS:", base_path)

        files_to_check = [
            "QtWebEngineProcess.exe",
            "resources/icudtl.dat",
            "resources/qtwebengine_resources.pak",
        ]

        for file in files_to_check:
            full_path = os.path.join(base_path, file)
            exists = os.path.exists(full_path)
            print(f"✓ {file}" if exists else f"✗ {file} - MISSING!")

    print("PATH:", os.environ.get("PATH", ""))
    print("QTWEBENGINEPROCESS_PATH:", os.environ.get("QTWEBENGINEPROCESS_PATH", "Not set"))


def fix_qt_dll():
    venv_path = os.path.dirname(sys.executable)
    site_packages = os.path.join(venv_path, "..", "Lib", "site-packages", "PyQt5", "Qt5", "bin")

    if os.path.exists(site_packages):
        os.environ["PATH"] = site_packages + os.pathsep + os.environ["PATH"]
        print(f"Добавлен путь: {site_packages}")

    try:
        from PyQt5 import QtCore  # noqa: F401

        print("✓ PyQt5 загружен успешно!")
        return True
    except ImportError as exc:
        print(f"✗ Ошибка: {exc}")
        return False


def setup_qt_webengine():
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    if getattr(sys, "frozen", False):
        base_path = sys._MEIPASS
        logger.info("Running in frozen mode, MEIPASS: %s", base_path)
    else:
        try:
            from PyQt5.QtCore import QLibraryInfo

            base_path = QLibraryInfo.location(QLibraryInfo.PrefixPath)
            logger.info("Running in dev mode, Qt path: %s", base_path)
        except ImportError:
            logger.error("PyQt5 not found in virtual environment!")
            return False

    webengine_process = os.path.join(base_path, "bin", "QtWebEngineProcess.exe")
    resources_path = os.path.join(base_path, "resources")

    if os.path.exists(webengine_process):
        os.environ["QTWEBENGINEPROCESS_PATH"] = webengine_process
        logger.info("Set QTWEBENGINEPROCESS_PATH: %s", webengine_process)
    else:
        logger.warning("QtWebEngineProcess.exe not found at: %s", webengine_process)

    if os.path.exists(resources_path):
        os.environ["QTWEBENGINE_RESOURCES_PATH"] = resources_path
        logger.info("Set QTWEBENGINE_RESOURCES_PATH: %s", resources_path)

    bin_path = os.path.join(base_path, "bin")
    if os.path.exists(bin_path) and bin_path not in os.environ["PATH"]:
        os.environ["PATH"] = bin_path + os.pathsep + os.environ["PATH"]
        logger.info("Added to PATH: %s", bin_path)

    return True


setup_qt_paths()

if not fix_qt_dll():
    sys.exit(1)

debug_qt_paths()
set_qt_plugin_path()

if not setup_qt_webengine():
    print("Failed to setup Qt WebEngine paths!")
    sys.exit(1)

try:
    from PyQt5.QtWidgets import QApplication
except ImportError as exc:
    print(f"Failed to import PyQt5: {exc}")
    print("Make sure PyQt5 and PyQtWebEngine are installed in your virtual environment!")
    sys.exit(1)

from config import DATA_DIR  # noqa: E402
from data_manager import DataManager  # noqa: E402
from map_app import MapApp  # noqa: E402


def ensure_offline_assets():
    try:
        import create_offline_assets

        print("Создание офлайн-ассетов...")
        create_offline_assets.create_offline_assets()
        print("Офлайн-ассеты созданы успешно")
    except Exception as exc:
        print(f"Ошибка создания ассетов: {exc}")


def main():
    ensure_offline_assets()
    data_manager = DataManager(DATA_DIR)
    app = QApplication(sys.argv)
    window = MapApp(data_manager)
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
