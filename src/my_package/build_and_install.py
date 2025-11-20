"""Утилита для автоматической установки зависимостей и сборки exe.

Запуск:
    python -m my_package.build_and_install

Скрипт:
* ставит зависимости из requirements.txt (включая PyInstaller),
* запускает существующий build_exe.py,
* проверяет, что ключевые файлы сборки лежат в output/Карта скважин.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
OUTPUT_DIR = PROJECT_ROOT.parent / "output"
DIST_DIR = OUTPUT_DIR / "Карта скважин"
REQUIREMENTS_FILE = BASE_DIR / "requirements.txt"
WARN_DIR = OUTPUT_DIR / "build" / "Карта скважин"


@dataclass
class CheckResult:
    name: str
    passed: bool
    details: str


def _run(cmd: list[str], *, cwd: Path | None = None) -> None:
    print(f"[run] {' '.join(cmd)}")
    subprocess.run(cmd, cwd=cwd, check=True)


def install_dependencies() -> None:
    """Установить зависимости, необходимые для сборки."""

    if not REQUIREMENTS_FILE.exists():
        raise FileNotFoundError(f"Не найден requirements.txt по пути {REQUIREMENTS_FILE}")

    _run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])
    _run([sys.executable, "-m", "pip", "install", "--no-warn-script-location", "-r", str(REQUIREMENTS_FILE)])


def _qt_process_candidates(base: Path) -> Iterable[Path]:
    process_name = "QtWebEngineProcess.exe" if sys.platform.startswith("win") else "QtWebEngineProcess"
    yield base / process_name
    yield base / "bin" / process_name
    yield base / "PyQt5" / "Qt" / "bin" / process_name
    yield base / "PyQt5" / "Qt" / "libexec" / process_name
    yield base / "PyQt5" / "Qt5" / "bin" / process_name
    yield base / "PyQt5" / "Qt5" / "libexec" / process_name


def verify_build_outputs() -> list[CheckResult]:
    checks: list[CheckResult] = []

    exe_path = DIST_DIR / "Карта скважин.exe"
    checks.append(
        CheckResult(
            name="EXE создан",
            passed=exe_path.exists(),
            details=str(exe_path),
        )
    )

    webengine_present = False
    for candidate in _qt_process_candidates(DIST_DIR):
        if candidate.exists():
            webengine_present = True
            break

    checks.append(
        CheckResult(
            name="QtWebEngineProcess доступен",
            passed=webengine_present,
            details="Файл найден в одной из стандартных папок" if webengine_present else "Файл не найден",
        )
    )

    warn_files = sorted(WARN_DIR.glob("warn-*.txt"))
    warn_lines: list[str] = []
    if warn_files:
        warn_path = warn_files[-1]
        warn_lines = [line.strip() for line in warn_path.read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip()]

    warn_details = "нет предупреждений"
    if warn_lines and warn_files:
        warn_details = f"есть предупреждения, см. {warn_files[-1].name}"

    checks.append(
        CheckResult(
            name="PyInstaller предупреждения",
            passed=len(warn_lines) == 0,
            details=warn_details,
        )
    )

    return checks


def print_checks(results: list[CheckResult]) -> None:
    print("\n=== Проверка сборки ===")
    for result in results:
        status = "[OK]" if result.passed else "[FAIL]"
        print(f"{status} {result.name}: {result.details}")


def main() -> None:
    print("Шаг 1. Установка зависимостей...")
    install_dependencies()

    print("Шаг 2. Сборка PyInstaller...")
    from build_exe import build

    build()

    print("Шаг 3. Проверка артефактов...")
    results = verify_build_outputs()
    print_checks(results)

    if not all(r.passed for r in results):
        raise SystemExit("Сборка завершилась, но найдены проблемы. Проверьте логи выше.")

    print("Готово! Сборка находится в папке:", DIST_DIR)


if __name__ == "__main__":
    main()
