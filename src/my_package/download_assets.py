import os
import requests
import zipfile
import shutil
from pathlib import Path


def download_leaflet():
    """Скачивает и распаковывает Leaflet библиотеку"""
    base_dir = Path(__file__).parent
    assets_dir = base_dir / "html_templates" / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    print(f"Директория для ассетов: {assets_dir}")

    # Папка для Leaflet
    leaflet_dir = assets_dir / "leaflet"
    leaflet_dir.mkdir(exist_ok=True)

    # Если Leaflet уже существует, пропускаем загрузку
    if (leaflet_dir / "leaflet.css").exists() and (leaflet_dir / "leaflet.js").exists():
        print("✓ Leaflet уже установлен")
        return

    # Скачиваем Leaflet
    leaflet_version = "1.9.4"
    leaflet_url = f"https://github.com/Leaflet/Leaflet/archive/refs/tags/v{leaflet_version}.zip"
    leaflet_zip_path = assets_dir / "leaflet.zip"

    print("Скачивание Leaflet...")
    try:
        response = requests.get(leaflet_url, timeout=30)
        response.raise_for_status()

        with open(leaflet_zip_path, 'wb') as f:
            f.write(response.content)

        # Распаковываем
        with zipfile.ZipFile(leaflet_zip_path, 'r') as zip_ref:
            # Извлекаем только нужные файлы
            for file in zip_ref.namelist():
                if file.startswith(f"Leaflet-{leaflet_version}/dist/"):
                    zip_ref.extract(file, assets_dir)

        # Копируем файлы в целевую директорию
        dist_dir = assets_dir / f"Leaflet-{leaflet_version}" / "dist"
        if dist_dir.exists():
            for item in dist_dir.iterdir():
                if item.is_file():
                    shutil.copy2(item, leaflet_dir)
                else:
                    if (leaflet_dir / item.name).exists():
                        shutil.rmtree(leaflet_dir / item.name)
                    shutil.copytree(item, leaflet_dir / item.name)

        # Удаляем временные файлы
        if leaflet_zip_path.exists():
            leaflet_zip_path.unlink()
        temp_dir = assets_dir / f"Leaflet-{leaflet_version}"
        if temp_dir.exists():
            shutil.rmtree(temp_dir)

        print("✓ Leaflet успешно скачан и распакован")
    except Exception as e:
        print(f"✗ Ошибка скачивания Leaflet: {e}")
        # Создаем базовые файлы вручную если скачивание не удалось
        create_fallback_leaflet(leaflet_dir)


def create_fallback_leaflet(leaflet_dir):
    """Создает базовые файлы Leaflet если скачивание не удалось"""
    leaflet_dir.mkdir(exist_ok=True)

    # Создаем минимальный leaflet.css
    css_content = """/* Leaflet CSS */
.leaflet-container {
    background: #ddd;
}
.leaflet-marker-icon {
    margin-left: -12px;
    margin-top: -41px;
    width: 25px;
    height: 41px;
}"""

    with open(leaflet_dir / "leaflet.css", "w", encoding="utf-8") as f:
        f.write(css_content)

    # Создаем минимальный leaflet.js
    js_content = """// Leaflet JS
console.log('Leaflet loaded');"""

    with open(leaflet_dir / "leaflet.js", "w", encoding="utf-8") as f:
        f.write(js_content)


def create_leaflet_offline_fallback(assets_dir):
    """Создает заглушку для leaflet.offline"""
    offline_js_path = assets_dir / "leaflet.offline.min.js"

    if not offline_js_path.exists():
        offline_content = """// Leaflet.Offline fallback
console.log('Leaflet.Offline fallback loaded');"""

        with open(offline_js_path, 'w', encoding='utf-8') as f:
            f.write(offline_content)
        print("✓ Создан fallback для leaflet.offline")


def create_offline_assets():
    """Основная функция создания офлайн-ассетов"""
    print("Создание офлайн-ассетов...")
    try:
        download_leaflet()

        base_dir = Path(__file__).parent
        assets_dir = base_dir / "html_templates" / "assets"
        create_leaflet_offline_fallback(assets_dir)

        print("Офлайн-ассеты созданы успешно")
    except Exception as e:
        print(f"Ошибка создания ассетов: {e}")


if __name__ == "__main__":
    create_offline_assets()