import os
import sys
from pathlib import Path


def _runtime_base() -> Path:
    """Возвращает корень ресурсов в рантайме.

    * В замороженном приложении (PyInstaller) файлы данных кладутся в ``_MEIPASS``
      или рядом с исполняемым файлом.
    * В режиме разработки используем каталог, где лежит текущий модуль.
    """

    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        return Path(sys.executable).resolve().parent

    return Path(__file__).resolve().parent


BASE_DIR = _runtime_base()
DATA_DIR = BASE_DIR / "data"
FILE_DIR = DATA_DIR / "files"
RESOURCES_DIR = BASE_DIR / "html_templates"

for directory in (DATA_DIR, FILE_DIR, RESOURCES_DIR):
    Path(directory).mkdir(parents=True, exist_ok=True)
