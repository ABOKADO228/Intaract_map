import os
import requests
from pathlib import Path


def download_offline_assets():
    """Скачивает необходимые JavaScript библиотеки для офлайн работы"""
    base_dir = Path(__file__).parent
    assets_dir = base_dir / "html_templates" / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    print(f"Директория для ассетов: {assets_dir}")

    # ПРАВИЛЬНЫЕ URL для leaflet.offline
    libraries = {
        "leaflet.offline.min.js": "https://raw.githubusercontent.com/robertomlsoares/leaflet.offline/master/dist/leaflet.offline.min.js",
    }
    # Добавьте этот список альтернативных URL
    alternative_urls = [
        "https://unpkg.com/leaflet.offline@1.4.0/dist/leaflet.offline.min.js",
        "https://cdn.jsdelivr.net/npm/leaflet.offline@1.4.0/leaflet.offline.min.js",
        ""
    ]
    for filename, url in libraries.items():
        filepath = assets_dir / filename
        print(f"Проверяем: {filename}")
        print(f"URL: {url}")

        if not filepath.exists():
            print(f"Скачивание {filename}...")
            try:
                response = requests.get(url, timeout=30)
                response.raise_for_status()

                with open(filepath, 'wb') as f:
                    f.write(response.content)

                print(f"✓ {filename} успешно скачан")
                print(f"Размер: {filepath.stat().st_size} байт")

            except Exception as e:
                print(f"✗ Ошибка скачивания {filename}: {e}")
                # Создаем заглушку
                create_fallback_file(filepath)
        else:
            file_size = filepath.stat().st_size
            print(f"✓ {filename} уже существует, размер: {file_size} байт")


def create_fallback_file(filepath):
    """Создает файл-заглушку если скачивание не удалось"""
    fallback_content = """// Leaflet.Offline fallback implementation
console.log('Leaflet.Offline fallback loaded');
L.TileLayer.Offline = L.TileLayer.extend({
    createTile: function(coords, done) {
        var tile = L.TileLayer.prototype.createTile.call(this, coords, done);
        var url = this.getTileUrl(coords);

        if (window.qt && window.qt.webChannelTransport && window.bridge) {
            window.bridge.getTile(url).then(function(dataUrl) {
                if (dataUrl && dataUrl.startsWith('data:')) {
                    var img = new Image();
                    img.onload = function() {
                        var ctx = tile.getContext('2d');
                        ctx.drawImage(img, 0, 0);
                        done(null, tile);
                    };
                    img.src = dataUrl;
                } else {
                    tile.onload = function() { done(null, tile); };
                    tile.onerror = function() { showOfflineTile(tile, done); };
                }
            }).catch(function() {
                tile.onload = function() { done(null, tile); };
                tile.onerror = function() { showOfflineTile(tile, done); };
            });
        } else {
            tile.onload = function() { done(null, tile); };
            tile.onerror = function() { showOfflineTile(tile, done); };
        }
        return tile;
    }
});

function showOfflineTile(tile, done) {
    var ctx = tile.getContext('2d');
    ctx.fillStyle = '#f8f9fa';
    ctx.fillRect(0, 0, 256, 256);
    ctx.fillStyle = '#6c757d';
    ctx.font = '12px Arial';
    ctx.textAlign = 'center';
    ctx.fillText('Офлайн', 128, 128);
    done(new Error('Offline mode'), tile);
}

L.tileLayer.offline = function(url, options) {
    return new L.TileLayer.Offline(url, options);
};
"""
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(fallback_content)
        print(f"✓ Создан fallback файл: {filepath}")
    except Exception as e:
        print(f"✗ Ошибка создания fallback: {e}")


if __name__ == "__main__":
    download_offline_assets()