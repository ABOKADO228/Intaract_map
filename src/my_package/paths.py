from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
FILE_DIR = DATA_DIR / "files"
RESOURCES_DIR = BASE_DIR / "html_templates"

for directory in (DATA_DIR, FILE_DIR, RESOURCES_DIR):
    directory.mkdir(parents=True, exist_ok=True)
