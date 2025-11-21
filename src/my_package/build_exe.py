import importlib.util
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


def _ensure_pyinstaller_loaded():
    """Импортировать PyInstaller, при необходимости попробовать локальную установку.

    В изолированных окружениях интернет-доступ может быть недоступен (403 proxy),
    поэтому позволяeм задать путь к заранее скачанному whl-файлу через
    ``PYINSTALLER_WHEEL``. Если переменная не указана, сохраняем прежнее поведение
    с явной ошибкой.
    """

    try:
        from PyInstaller.__main__ import run as pyinstaller_run  # type: ignore
        from PyInstaller.utils.hooks import collect_data_files  # type: ignore

        return pyinstaller_run, collect_data_files
    except ImportError:
        wheel_path = os.environ.get("PYINSTALLER_WHEEL")
        if wheel_path:
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", wheel_path])
            except subprocess.CalledProcessError as exc:  # pragma: no cover - runtime guard
                raise SystemExit(
                    "PyInstaller не найден, и установка из PYINSTALLER_WHEEL завершилась ошибкой."
                ) from exc

            from PyInstaller.__main__ import run as pyinstaller_run  # type: ignore
            from PyInstaller.utils.hooks import collect_data_files  # type: ignore

            return pyinstaller_run, collect_data_files

        raise SystemExit(
            "PyInstaller не установлен. Установите его перед сборкой (pip install pyinstaller) "
            "или укажите путь к локальному whl в переменной PYINSTALLER_WHEEL."
        )


pyinstaller_run, collect_data_files = _ensure_pyinstaller_loaded()

try:
    import PyQt5
except ImportError as exc:  # pragma: no cover - handled at runtime
    raise SystemExit("PyQt5 не найден. Установите зависимости из requirements.txt.") from exc

def _import_sip_or_alias() -> None:
    """Импортировать sip, если нужно — зарегистрировать alias из PyQt5."""

    try:
        import sip  # type: ignore

        return
    except ImportError:
        pass

    try:
        from PyQt5 import sip as pyqt_sip  # type: ignore

        sys.modules["sip"] = pyqt_sip
    except ImportError as exc:  # pragma: no cover - handled at runtime
        raise SystemExit(
            "Модуль sip не найден. Убедитесь, что установлены зависимости (pip install -r requirements.txt)."
        ) from exc


_import_sip_or_alias()

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
OUTPUT_DIR = PROJECT_ROOT.parent / "output"
BUILD_DIR = OUTPUT_DIR / "build"
SPEC_DIR = OUTPUT_DIR
ENTRY_POINT = BASE_DIR / "Карта скважин.py"

EXCLUDED_MODULES: list[str] = [
    # Стандартные posix-модули, которых нет на Windows. PyInstaller пытается
    # анализировать их, поэтому явно исключаем, чтобы не получать warn-лог.
    "pwd",
    "grp",
    "posix",
    "resource",
    "_posixsubprocess",
    "_posixshmem",
    "fcntl",
    "termios",
    "_scproxy",
    "_frozen_importlib",
    "_frozen_importlib_external",
    "_winreg",
    "readline",
    "vms_lib",
    "java",
    "java.lang",
    # Опциональные зависимости requests/urllib3, которые нам не нужны в рантайме.
    "simplejson",
    "chardet",
    "brotli",
    "brotlicffi",
    "socks",
    "pyodide",
    "js",
    "zstandard",
    "compression",
    "h2",
    "h2.events",
    "h2.connection",
    "h2.config",
    "OpenSSL",
    "OpenSSL.crypto",
    "OpenSSL.SSL",
    "cryptography",
    "cryptography.x509",
    "cryptography.x509.extensions",
    "pyimod02_importers",
    "dummy_threading",
    "annotationlib",
    "multiprocessing.BufferTooShort",
    "multiprocessing.AuthenticationError",
    "multiprocessing.get_context",
    "multiprocessing.TimeoutError",
    "multiprocessing.set_start_method",
    "multiprocessing.get_start_method",
]


def _as_data_arg(source: Path, target: str) -> list[str]:
    return ["--add-data", f"{source}{os.pathsep}{target}"]


def _as_binary_arg(source: Path, target: str) -> list[str]:
    return ["--add-binary", f"{source}{os.pathsep}{target}"]


def _first_existing(paths: Iterable[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


@dataclass
class QtLayout:
    qt_path: Path
    bin_dir: Path
    libexec_dir: Path
    resources_dir: Path
    webengine_process: Path

    @property
    def qt_dir_name(self) -> str:
        return self.qt_path.name


def _discover_qt_layout() -> QtLayout:
    qt_root = Path(PyQt5.__file__).parent
    qt_path = _first_existing([qt_root / "Qt5", qt_root / "Qt"])

    if qt_path is None:
        raise FileNotFoundError("Не удалось найти каталог Qt в установке PyQt5")

    bin_dir = qt_path / "bin"
    libexec_dir = qt_path / "libexec"
    resources_dir = qt_path / "resources"

    process_candidates = [
        bin_dir / ("QtWebEngineProcess.exe" if os.name == "nt" else "QtWebEngineProcess"),
        libexec_dir / ("QtWebEngineProcess.exe" if os.name == "nt" else "QtWebEngineProcess"),
    ]

    webengine_process = _first_existing(process_candidates)
    if webengine_process is None:
        search = list(qt_path.rglob("QtWebEngineProcess*"))
        webengine_process = search[0] if search else None

    if webengine_process is None:
        raise FileNotFoundError("QtWebEngineProcess не найден. Проверьте установку PyQt5 и QtWebEngine.")

    return QtLayout(
        qt_path=qt_path,
        bin_dir=bin_dir,
        libexec_dir=libexec_dir,
        resources_dir=resources_dir,
        webengine_process=webengine_process,
    )


def _gather_qt_resources(layout: QtLayout) -> tuple[list[str], list[str]]:
    data_args: list[str] = []
    binary_args: list[str] = []

    # Всегда копируем в bin и libexec, так как разные версии Qt ищут бинарь в обоих местах
    qt_dir_name = layout.qt_dir_name
    binary_args.extend(_as_binary_arg(layout.webengine_process, f"PyQt5/{qt_dir_name}/bin"))
    binary_args.extend(_as_binary_arg(layout.webengine_process, f"PyQt5/{qt_dir_name}/libexec"))
    # add a fallback copy near the root to satisfy runtime lookups in some environments
    binary_args.extend(_as_binary_arg(layout.webengine_process, "."))

    for resource_name in (
        "icudtl.dat",
        "qtwebengine_resources.pak",
        "qtwebengine_resources_100p.pak",
        "qtwebengine_resources_200p.pak",
    ):
        resource_path = layout.resources_dir / resource_name
        if resource_path.exists():
            data_args.extend(_as_data_arg(resource_path, f"PyQt5/{qt_dir_name}/resources"))
            # duplicate in top-level resources to match runtime search paths
            data_args.extend(_as_data_arg(resource_path, "resources"))

    spec = importlib.util.find_spec("PyQt5.QtWebEngineWidgets")
    if spec and spec.submodule_search_locations:
        for source, target in collect_data_files("PyQt5.QtWebEngineWidgets"):
            data_args.extend(_as_data_arg(Path(source), target))

    return data_args, binary_args


def _ensure_webengine_in_dist(layout: QtLayout, dist_dir: Path) -> None:
    """Дублируем QtWebEngineProcess и ресурсы прямо в папку сборки после PyInstaller.

    Иногда PyInstaller не раскладывает бинарь в ожидаемые подпапки (из-за прав или
    нестандартного расположения Qt). Этот шаг копирует проверенные файлы напрямую
    в dist, чтобы рантайм всегда находил WebEngine.
    """

    qt_dir_name = layout.qt_dir_name
    targets = [
        dist_dir / f"PyQt5/{qt_dir_name}/bin/{layout.webengine_process.name}",
        dist_dir / f"PyQt5/{qt_dir_name}/libexec/{layout.webengine_process.name}",
        dist_dir / layout.webengine_process.name,
    ]

    for target in targets:
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.write_bytes(layout.webengine_process.read_bytes())

    # Дублируем ключевые ресурсы QtWebEngine
    for resource_name in (
        "icudtl.dat",
        "qtwebengine_resources.pak",
        "qtwebengine_resources_100p.pak",
        "qtwebengine_resources_200p.pak",
    ):
        src = layout.resources_dir / resource_name
        if not src.exists():
            continue

        for target in (
            dist_dir / f"PyQt5/{qt_dir_name}/resources/{resource_name}",
            dist_dir / f"resources/{resource_name}",
        ):
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                target.write_bytes(src.read_bytes())


def _prepare_ascii_entry_point() -> Path:
    """Создать временный entry-point без кириллицы для PyInstaller.

    На некоторых системах PyInstaller падает, если скрипт запуска или имя exe
    содержат не-ASCII символы. Чтобы избежать сбоев при сборке, создаём
    вспомогательный скрипт с безопасным именем в каталоге ``build`` и указываем
    его PyInstaller вместо оригинального файла с кириллицей.
    """

    wrapper_path = BUILD_DIR / "app_entry.py"
    wrapper_code = f"""import pathlib, runpy, sys

ENTRY = pathlib.Path(r"{ENTRY_POINT}")

if not ENTRY.exists():
    raise FileNotFoundError(f"Не найден основной скрипт: {ENTRY}")

runpy.run_path(str(ENTRY), run_name='__main__')
"""

    wrapper_path.write_text(wrapper_code, encoding="utf-8")
    return wrapper_path


def build():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    BUILD_DIR.mkdir(parents=True, exist_ok=True)

    dist_dir = OUTPUT_DIR / "Карта скважин"
    if dist_dir.exists():
        try:
            shutil.rmtree(dist_dir)
        except OSError as exc:
            raise SystemExit(
                "Не удалось удалить предыдущую сборку. Закройте запущенный exe "
                "и повторите попытку (ошибка при очистке dist)."
            ) from exc

    # Чтобы избежать ошибок доступа при повторной сборке, удаляем старый exe,
    # если он остался запущенным или заблокированным антивирусом.
    existing_exe = OUTPUT_DIR / "Карта скважин" / "Карта скважин.exe"
    if existing_exe.exists():
        try:
            existing_exe.unlink()
        except OSError:
            # Не критично: PyInstaller всё равно попробует перезаписать файл,
            # но предупреждение PermissionError появляться будет реже.
            pass

    layout = _discover_qt_layout()

    data_args = []
    binary_args = []

    # Пользовательские ресурсы приложения
    data_args.extend(_as_data_arg(BASE_DIR / "html_templates", "html_templates"))
    data_args.extend(_as_data_arg(BASE_DIR / "data", "data"))

    qt_data_args, qt_binary_args = _gather_qt_resources(layout)
    data_args.extend(qt_data_args)
    binary_args.extend(qt_binary_args)

    # PyInstaller может некорректно обрабатывать пути с кириллицей. Передаем
    # обертку с латинским именем, чтобы исключить ошибки кодировки.
    entry_point = _prepare_ascii_entry_point()

    args = [
        "--noconfirm",
        "--clean",
        "--onedir",
        f"--name=Карта скважин",
        f"--distpath={OUTPUT_DIR}",
        f"--workpath={BUILD_DIR}",
        f"--specpath={SPEC_DIR}",
        f"--paths={BASE_DIR}",
        "--hidden-import=PyQt5.QtWebEngineWidgets",
        "--hidden-import=PyQt5.QtWebEngine",  # гарантирует подтягивание webengine
        "--hidden-import=PyQt5.QtWebEngineCore",
        "--hidden-import=PyQt5.sip",
        "--hidden-import=sip",
    ]

    for module in EXCLUDED_MODULES:
        args.append(f"--exclude-module={module}")

    args += data_args + binary_args
    args.append(str(entry_point))

    pyinstaller_run(args)

    # Дополнительная страховка: если PyInstaller не разложил WebEngine,
    # продублируем файлы напрямую в dist.
    _ensure_webengine_in_dist(layout, dist_dir)

    # Чистим вспомогательный entry-point, чтобы не оставлять временный
    # файл между сборками и не путать PyInstaller при следующем запуске.
    try:
        entry_point.unlink()
    except OSError:
        pass


if __name__ == "__main__":
    build()
