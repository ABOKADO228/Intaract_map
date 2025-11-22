import logging
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.*=false;qt.css.*=false")


def _frozen_base() -> Path:
    """Возвращает корень упакованного приложения или каталог модуля."""

    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))

    return Path(__file__).resolve().parent


def set_qt_plugin_path():
    if getattr(sys, "frozen", False):
        base_path = _frozen_base()
        plugin_candidates = [
            base_path / "qt5_plugins",
            base_path / "plugins",
            base_path / "PyQt5" / "Qt" / "plugins",
            base_path / "PyQt5" / "Qt5" / "plugins",
        ]

        for candidate in plugin_candidates:
            if candidate.is_dir():
                os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = str(candidate).replace("\\", "/")
                break

        process_candidates = [
            base_path / "bin" / "QtWebEngineProcess.exe",
            base_path / "QtWebEngineProcess.exe",
            base_path / "PyQt5" / "Qt" / "bin" / "QtWebEngineProcess.exe",
            base_path / "PyQt5" / "Qt" / "libexec" / "QtWebEngineProcess.exe",
            base_path / "PyQt5" / "Qt5" / "bin" / "QtWebEngineProcess.exe",
            base_path / "PyQt5" / "Qt5" / "libexec" / "QtWebEngineProcess.exe",
        ]

        for process_path in process_candidates:
            if process_path.exists():
                os.environ["QTWEBENGINEPROCESS_PATH"] = str(process_path).replace("\\", "/")
                break


def setup_qt_paths():
    if getattr(sys, "frozen", False):
        base_path = _frozen_base()

        qt_paths = [
            base_path / "bin",
            base_path / "plugins",
            base_path / "resources",
            base_path / "PyQt5" / "Qt" / "bin",
            base_path / "PyQt5" / "Qt5" / "bin",
        ]

        for path in qt_paths:
            if path.exists() and str(path) not in os.environ["PATH"]:
                os.environ["PATH"] = str(path) + os.pathsep + os.environ["PATH"]

        process_candidates = [
            base_path / "QtWebEngineProcess.exe",
            base_path / "bin" / "QtWebEngineProcess.exe",
            base_path / "PyQt5" / "Qt" / "bin" / "QtWebEngineProcess.exe",
            base_path / "PyQt5" / "Qt" / "libexec" / "QtWebEngineProcess.exe",
            base_path / "PyQt5" / "Qt5" / "bin" / "QtWebEngineProcess.exe",
            base_path / "PyQt5" / "Qt5" / "libexec" / "QtWebEngineProcess.exe",
        ]

        for webengine_process in process_candidates:
            if webengine_process.exists():
                os.environ["QTWEBENGINEPROCESS_PATH"] = str(webengine_process)
                break

        os.environ["QTWEBENGINE_RESOURCES_PATH"] = str(base_path / "resources")


def debug_qt_paths():
    """Печать отладочной информации Qt (по умолчанию только в frozen-сборке)."""

    if not getattr(sys, "frozen", False) and os.environ.get("QT_DEBUG_INFO", "").lower() not in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return

    print("=== QT DEBUG INFO ===")
    print("Frozen:", getattr(sys, "frozen", False))

    if getattr(sys, "frozen", False):
        base_path = _frozen_base()
        print("Base:", base_path)

        files_to_check = [
            "QtWebEngineProcess.exe",
            "resources/icudtl.dat",
            "resources/qtwebengine_resources.pak",
        ]

        for file in files_to_check:
            full_path = base_path / file
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

    def _first_existing(paths):
        for item in paths:
            if os.path.exists(item):
                return item
        return None

    if getattr(sys, "frozen", False):
        base_path = _frozen_base()
        logger.info("Running in frozen mode, MEIPASS: %s", base_path)
    else:
        try:
            from PyQt5.QtCore import QLibraryInfo

            base_path = QLibraryInfo.location(QLibraryInfo.PrefixPath)
            logger.info("Running in dev mode, Qt path: %s", base_path)
        except ImportError:
            logger.error("PyQt5 not found in virtual environment!")
            return False

    process_candidates = [
        base_path / "QtWebEngineProcess.exe",
        base_path / "bin" / "QtWebEngineProcess.exe",
        base_path / "PyQt5" / "Qt" / "bin" / "QtWebEngineProcess.exe",
        base_path / "PyQt5" / "Qt" / "libexec" / "QtWebEngineProcess.exe",
        base_path / "PyQt5" / "Qt5" / "bin" / "QtWebEngineProcess.exe",
        base_path / "PyQt5" / "Qt5" / "libexec" / "QtWebEngineProcess.exe",
    ]

    webengine_process = _first_existing(process_candidates)
    if webengine_process:
        os.environ["QTWEBENGINEPROCESS_PATH"] = str(webengine_process)
        logger.info("Set QTWEBENGINEPROCESS_PATH: %s", webengine_process)
    else:
        logger.error(
            "QtWebEngineProcess.exe not found in any of: %s",
            ", ".join(map(str, process_candidates)),
        )

    resource_candidates = [
        base_path / "resources",
        base_path / "PyQt5" / "Qt" / "resources",
        base_path / "PyQt5" / "Qt5" / "resources",
    ]

    resources_path = _first_existing(resource_candidates)
    if resources_path:
        os.environ["QTWEBENGINE_RESOURCES_PATH"] = str(resources_path)
        logger.info("Set QTWEBENGINE_RESOURCES_PATH: %s", resources_path)
    else:
        logger.error(
            "Qt WebEngine resources not found in any of: %s",
            ", ".join(map(str, resource_candidates)),
        )

    bin_candidates = [
        base_path / "bin",
        base_path / "PyQt5" / "Qt" / "bin",
        base_path / "PyQt5" / "Qt5" / "bin",
    ]

    current_path = os.environ.get("PATH") or ""
    for bin_path in bin_candidates:
        if os.path.exists(bin_path) and str(bin_path) not in current_path:
            current_path = str(bin_path) + os.pathsep + current_path
            logger.info("Added to PATH: %s", bin_path)

    os.environ["PATH"] = current_path

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

from config import DATA_DIR, RESOURCES_DIR  # noqa: E402
from data_manager import DataManager  # noqa: E402
from map_app import MapApp  # noqa: E402


def ensure_offline_assets():
    assets_dir = Path(RESOURCES_DIR) / "assets" / "leaflet"
    if (assets_dir / "leaflet.css").exists() and (assets_dir / "leaflet.js").exists():
        return

    try:
        import create_offline_assets

        create_offline_assets.create_offline_assets()
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
