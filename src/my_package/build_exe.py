import importlib.util
import os
from pathlib import Path
from typing import Iterable

try:
    from PyInstaller.__main__ import run as pyinstaller_run
    from PyInstaller.utils.hooks import collect_data_files
except ImportError as exc:  # pragma: no cover - handled at runtime
    raise SystemExit(
        "PyInstaller не установлен. Установите его перед сборкой (pip install pyinstaller)."
    ) from exc

try:
    import PyQt5
except ImportError as exc:  # pragma: no cover - handled at runtime
    raise SystemExit("PyQt5 не найден. Установите зависимости из requirements.txt.") from exc

try:
    import sip
except ImportError as exc:  # pragma: no cover - handled at runtime
    raise SystemExit(
        "Модуль sip не найден. Убедитесь, что установлены зависимости (pip install -r requirements.txt)."
    ) from exc

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
    "fcntl",
    "termios",
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
    "OpenSSL",
    "cryptography",
    "cryptography.x509",
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


def _gather_qt_resources() -> tuple[list[str], list[str]]:
    qt_root = Path(PyQt5.__file__).parent
    # PyQt5 может устанавливать Qt как "Qt" или "Qt5" в site-packages
    qt_path = _first_existing([qt_root / "Qt5", qt_root / "Qt"])

    if qt_path is None:
        raise FileNotFoundError("Не удалось найти каталог Qt в установке PyQt5")

    resources = qt_path / "resources"
    bin_dir = qt_path / "bin"
    libexec_dir = qt_path / "libexec"
    webengine_candidates = [
        bin_dir / ("QtWebEngineProcess.exe" if os.name == "nt" else "QtWebEngineProcess"),
        libexec_dir / ("QtWebEngineProcess.exe" if os.name == "nt" else "QtWebEngineProcess"),
    ]

    data_args: list[str] = []
    binary_args: list[str] = []

    webengine_process = _first_existing(webengine_candidates)
    if webengine_process is None:
        search = list(qt_path.rglob("QtWebEngineProcess*"))
        webengine_process = search[0] if search else None

    if webengine_process:
        # Всегда копируем в bin и libexec, так как разные версии Qt ищут бинарь в обоих местах
        qt_dir_name = qt_path.name
        binary_args.extend(_as_binary_arg(webengine_process, f"PyQt5/{qt_dir_name}/bin"))
        binary_args.extend(_as_binary_arg(webengine_process, f"PyQt5/{qt_dir_name}/libexec"))
        # add a fallback copy near the root to satisfy runtime lookups in some environments
        binary_args.extend(_as_binary_arg(webengine_process, "."))
    else:  # pragma: no cover - defensive branch
        raise FileNotFoundError(
            "QtWebEngineProcess не найден. Проверьте установку PyQt5 и QtWebEngine."
        )

    for resource_name in (
        "icudtl.dat",
        "qtwebengine_resources.pak",
        "qtwebengine_resources_100p.pak",
        "qtwebengine_resources_200p.pak",
    ):
        resource_path = resources / resource_name
        if resource_path.exists():
            data_args.extend(_as_data_arg(resource_path, "PyQt5/Qt/resources"))

    spec = importlib.util.find_spec("PyQt5.QtWebEngineWidgets")
    if spec and spec.submodule_search_locations:
        for source, target in collect_data_files("PyQt5.QtWebEngineWidgets"):
            data_args.extend(_as_data_arg(Path(source), target))

    return data_args, binary_args


def build():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    BUILD_DIR.mkdir(parents=True, exist_ok=True)

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

    data_args = []
    binary_args = []

    # Пользовательские ресурсы приложения
    data_args.extend(_as_data_arg(BASE_DIR / "html_templates", "html_templates"))
    data_args.extend(_as_data_arg(BASE_DIR / "data", "data"))

    qt_data_args, qt_binary_args = _gather_qt_resources()
    data_args.extend(qt_data_args)
    binary_args.extend(qt_binary_args)

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
    args.append(str(ENTRY_POINT))

    pyinstaller_run(args)


if __name__ == "__main__":
    build()
