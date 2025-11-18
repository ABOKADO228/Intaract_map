from pathlib import Path


def create_offline_assets():
    """Создает офлайн-ассеты без скачивания из интернета"""
    base_dir = Path(__file__).parent
    assets_dir = base_dir / "html_templates" / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    # Создаем полнофункциональный leaflet.offline
    offline_js_content = """// Leaflet.Offline custom implementation
(function() {
    'use strict';

    L.TileLayer.Offline = L.TileLayer.extend({
        initialize: function(url, options) {
            L.TileLayer.prototype.initialize.call(this, url, options);
            this._offlineTiles = {};
        },

        createTile: function(coords, done) {
            var tile = L.DomUtil.create('canvas', 'leaflet-tile');
            var size = this.getTileSize();
            tile.width = size.x;
            tile.height = size.y;

            var url = this.getTileUrl(coords);
            var self = this;

            // Пытаемся получить тайл из кэша
            if (window.qt && window.qt.webChannelTransport && window.bridge) {
                window.bridge.getTile(url).then(function(dataUrl) {
                    if (dataUrl && dataUrl.startsWith('data:')) {
                        var img = new Image();
                        img.onload = function() {
                            var ctx = tile.getContext('2d');
                            ctx.drawImage(img, 0, 0);
                            done(null, tile);
                        };
                        img.onerror = function() {
                            self._showOfflineTile(tile, done);
                        };
                        img.src = dataUrl;
                    } else {
                        self._loadOnlineTile(tile, url, done);
                    }
                }).catch(function() {
                    self._loadOnlineTile(tile, url, done);
                });
            } else {
                self._loadOnlineTile(tile, url, done);
            }

            return tile;
        },

        _loadOnlineTile: function(tile, url, done) {
            var img = new Image();
            var self = this;

            img.onload = function() {
                var ctx = tile.getContext('2d');
                ctx.drawImage(img, 0, 0);
                done(null, tile);
            };

            img.onerror = function() {
                self._showOfflineTile(tile, done);
            };

            img.crossOrigin = 'anonymous';
            img.src = url;
        },

        _showOfflineTile: function(tile, done) {
            var ctx = tile.getContext('2d');
            var size = this.getTileSize();

            // Создаем красивый офлайн-тайл
            ctx.fillStyle = '#f8f9fa';
            ctx.fillRect(0, 0, size.x, size.y);

            // Рамка
            ctx.strokeStyle = '#dee2e6';
            ctx.lineWidth = 1;
            ctx.strokeRect(0, 0, size.x, size.y);

            // Текст
            ctx.fillStyle = '#6c757d';
            ctx.font = 'bold 14px Arial, sans-serif';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText('ОФЛАЙН', size.x / 2, size.y / 2 - 10);

            ctx.font = '10px Arial, sans-serif';
            ctx.fillText('Карта недоступна', size.x / 2, size.y / 2 + 10);

            done(new Error('Offline mode'), tile);
        }
    });

    L.tileLayer.offline = function(url, options) {
        return new L.TileLayer.Offline(url, options);
    };
})();
"""

    filepath = assets_dir / "leaflet.offline.min.js"

    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(offline_js_content)
        print("✓ Успешно создан leaflet.offline.min.js")
        print(f"✓ Файл сохранен: {filepath}")
        print(f"✓ Размер: {len(offline_js_content)} символов")
    except Exception as e:
        print(f"✗ Ошибка создания файла: {e}")


if __name__ == "__main__":
    create_offline_assets()