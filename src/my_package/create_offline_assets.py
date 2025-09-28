from pathlib import Path


def create_offline_assets():
    """Создает офлайн-ассеты"""
    base_dir = Path(__file__).parent
    assets_dir = base_dir / "html_templates" / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    # Создаем полнофункциональный офлайн-менеджер для тайлов
    offline_js_content = """// Leaflet.Offline custom implementation
(function() {
    'use strict';

    // Создаем кастомный офлайн-слой (НИКОГДА не использует интернет)
    L.TileLayer.Offline = L.TileLayer.extend({
        initialize: function(url, options) {
            // Игнорируем URL, так как мы не используем интернет
            L.TileLayer.prototype.initialize.call(this, '', options);
        },

        createTile: function(coords, done) {
            var tile = document.createElement('img');
            var self = this;

            // Генерируем URL для этого тайла (для поиска в кэше)
            var url = 'https://cartodb-basemaps-a.global.ssl.fastly.net/rastertiles/voyager/' + 
                     coords.z + '/' + coords.x + '/' + coords.y + '.png';

            // Всегда пытаемся получить тайл из кэша через bridge
            if (window.qt && window.qt.webChannelTransport && window.bridge) {
                window.bridge.getTile(url).then(function(dataUrl) {
                    if (dataUrl && dataUrl.startsWith('data:')) {
                        // Тайл найден в кэше - используем его
                        tile.onload = function() {
                            done(null, tile);
                        };
                        tile.onerror = function() {
                            self._showOfflineTile(tile, done);
                        };
                        tile.src = dataUrl;
                    } else {
                        // Тайла нет в кэше - показываем офлайн-тайл
                        self._showOfflineTile(tile, done);
                    }
                }).catch(function(error) {
                    console.log('Ошибка получения тайла:', error);
                    self._showOfflineTile(tile, done);
                });
            } else {
                // WebChannel не доступен - показываем офлайн-тайл
                self._showOfflineTile(tile, done);
            }

            return tile;
        },

        _showOfflineTile: function(tile, done) {
            // Создаем canvas для офлайн-тайла
            var canvas = document.createElement('canvas');
            canvas.width = 256;
            canvas.height = 256;
            var ctx = canvas.getContext('2d');

            // Создаем красивый офлайн-тайл
            ctx.fillStyle = '#f8f9fa';
            ctx.fillRect(0, 0, 256, 256);

            // Рамка
            ctx.strokeStyle = '#dee2e6';
            ctx.lineWidth = 1;
            ctx.strokeRect(0, 0, 256, 256);

            // Текст
            ctx.fillStyle = '#6c757d';
            ctx.font = 'bold 14px Arial, sans-serif';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText('ОФЛАЙН', 128, 128 - 10);

            ctx.font = '10px Arial, sans-serif';
            ctx.fillText('Используйте кэшированные тайлы', 128, 128 + 10);

            // Конвертируем canvas в data URL и устанавливаем как src
            tile.onload = function() {
                done(null, tile);
            };
            tile.onerror = function() {
                done(new Error('Offline tile error'), tile);
            };
            tile.src = canvas.toDataURL();
        }
    });

    L.tileLayer.offline = function(options) {
        return new L.TileLayer.Offline('', options);
    };

    // Создаем онлайн-слой для случаев, когда нужны свежие тайлы
    L.TileLayer.Online = L.TileLayer.extend({
        initialize: function(url, options) {
            L.TileLayer.prototype.initialize.call(this, url, options);
        },

        createTile: function(coords, done) {
            var tile = L.DomUtil.create('img', 'leaflet-tile');
            var url = this.getTileUrl(coords);
            var self = this;

            tile.onload = function() {
                done(null, tile);
            };

            tile.onerror = function() {
                // При ошибке загрузки пытаемся получить из кэша
                if (window.qt && window.qt.webChannelTransport && window.bridge) {
                    window.bridge.getTile(url).then(function(dataUrl) {
                        if (dataUrl && dataUrl.startsWith('data:')) {
                            tile.src = dataUrl;
                        } else {
                            // Если в кэше нет, показываем офлайн-тайл
                            self._showErrorTile(tile, done);
                        }
                    }).catch(function() {
                        self._showErrorTile(tile, done);
                    });
                } else {
                    self._showErrorTile(tile, done);
                }
            };

            tile.crossOrigin = 'anonymous';
            tile.src = url;
            return tile;
        },

        _showErrorTile: function(tile, done) {
            var canvas = document.createElement('canvas');
            canvas.width = 256;
            canvas.height = 256;
            var ctx = canvas.getContext('2d');
            ctx.fillStyle = '#fff3cd';
            ctx.fillRect(0, 0, 256, 256);
            ctx.fillStyle = '#856404';
            ctx.font = '12px Arial';
            ctx.textAlign = 'center';
            ctx.fillText('Ошибка загрузки', 128, 128);
            tile.onload = function() {
                done(null, tile);
            };
            tile.src = canvas.toDataURL();
        }
    });

    L.tileLayer.online = function(url, options) {
        return new L.TileLayer.Online(url, options);
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