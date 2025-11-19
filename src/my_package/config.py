import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = os.path.join(BASE_DIR, "data")
FILE_DIR = os.path.join(DATA_DIR, "files")
RESOURCES_DIR = os.path.join(BASE_DIR, "html_templates")

for directory in (DATA_DIR, FILE_DIR, RESOURCES_DIR):
    os.makedirs(directory, exist_ok=True)
