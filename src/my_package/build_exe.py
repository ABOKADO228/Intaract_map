import os
from pathlib import Path

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

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
OUTPUT_DIR = PROJECT_ROOT.parent / "output"
BUILD_DIR = OUTPUT_DIR / "build"
SPEC_DIR = OUTPUT_DIR
ENTRY_POINT = BASE_DIR / "Карта скважин.py"


def _as_data_arg(source: Path, target: str) -> list[str]:
    return ["--add-data", f"{source}{os.pathsep}{target}"]


def _as_binary_arg(source: Path, target: str) -> list[str]:
    return ["--add-binary", f"{source}{os.pathsep}{target}"]


def _gather_qt_resources() -> tuple[list[str], list[str]]:
    qt_path = Path(PyQt5.__file__).parent / "Qt"

    resources = qt_path / "resources"
    bin_dir = qt_path / ("bin" if (qt_path / "bin").exists() else "libexec")
    webengine_process = bin_dir / ("QtWebEngineProcess.exe" if os.name == "nt" else "QtWebEngineProcess")

    data_args: list[str] = []
    binary_args: list[str] = []

    if webengine_process.exists():
        binary_args.extend(_as_binary_arg(webengine_process, "PyQt5/Qt/bin"))

    for resource_name in (
        "icudtl.dat",
        "qtwebengine_resources.pak",
        "qtwebengine_resources_100p.pak",
        "qtwebengine_resources_200p.pak",
    ):
        resource_path = resources / resource_name
        if resource_path.exists():
            data_args.extend(_as_data_arg(resource_path, "PyQt5/Qt/resources"))

    for source, target in collect_data_files("PyQt5.QtWebEngineWidgets"):
        data_args.extend(_as_data_arg(Path(source), target))

    return data_args, binary_args


def build():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    BUILD_DIR.mkdir(parents=True, exist_ok=True)

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
    ]

    args += data_args + binary_args
    args.append(str(ENTRY_POINT))

    pyinstaller_run(args)


if __name__ == "__main__":
    build()
