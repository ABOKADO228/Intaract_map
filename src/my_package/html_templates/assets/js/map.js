// Функция для экранирования HTML (защита от XSS)
function escapeHtml(unsafe) {
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// Инициализация карты
var map = L.map('map', {minZoom: 0, maxZoom: 18, preferCanvas: true}).setView([59.93, 30.34], 12);
var markers = L.layerGroup().addTo(map);
var selectedMarkerIds = [];
var markerData = [];
const markerIndex = new Map();

let navTreeScheduled = false;
let selectedListScheduled = false;

function getMarkerById(id) {
    return markerIndex.get(id) || markerData.find(function(marker) { return marker.id === id; });
}

function getSelectedMarkerIds() {
    return selectedMarkerIds.slice();
}

var bridge = null;
var mapInitialized = false;
var colorChangeQueue = [];
var colorChangeTimer = null;
var currentLayer = null;
var currentMode = null;
var connectivityState = {
    isOnline: false,
    lastChecked: 0
};
var webChannelInstance = null;

function setBridge(instance) {
    if (instance) {
        bridge = instance;
        window.bridge = instance;
    }
}

function getBridge() {
    return window.bridge || bridge;
}

function getTileFromBridge(url) {
    try {
        var activeBridge = getBridge();
        if (!activeBridge || typeof activeBridge.getTile !== 'function') {
            return Promise.resolve('');
        }

        var result = activeBridge.getTile(url);
        if (result && typeof result.then === 'function') {
            return result;
        }

        return Promise.resolve(result);
    } catch (error) {
        console.error('Ошибка обращения к bridge.getTile:', error);
        return Promise.resolve('');
    }
}

// CartoDB Voyager конфигурация
var cartoDBVoyager = {
online: {
    url: 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png',
    options: {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
        subdomains: 'abcd',
        minZoom: 0, maxZoom: 18
    }
}
};

// Оптимизированный офлайн-слой
var OfflineTileLayer = L.TileLayer.extend({
    initialize: function(options) {
        L.TileLayer.prototype.initialize.call(this, '', options);
        this._tileCache = {};
    },

createTile: function (coords, done) {
    var tile = L.DomUtil.create('canvas', 'leaflet-tile');
    var ctx = tile.getContext('2d');
    var size = this.getTileSize();
    tile.width = size.x;
    tile.height = size.y;

    var url = this.getTileUrl(coords);

    // Проверяем кэш сначала
    if (this._tileCache[url]) {
        var img = new Image();
        img.onload = function() {
            ctx.drawImage(img, 0, 0);
            done(null, tile);
        };
        img.src = this._tileCache[url];
        return tile;
    }

    // Запрашиваем тайл через bridge
    if (getBridge()) {
        getTileFromBridge(url)
            .then(function(dataUrl) {
                if (dataUrl && dataUrl.startsWith('data:')) {
                    // Сохраняем в кэш
                    this._tileCache[url] = dataUrl;

                    var img = new Image();
                    img.onload = function() {
                        ctx.drawImage(img, 0, 0);
                        done(null, tile);
                    };
                    img.onerror = function() {
                        showOfflineTile(tile, done);
                    };
                    img.src = dataUrl;
                } else {
                    showOfflineTile(tile, done);
                }
            }.bind(this))
            .catch(function(error) {
                console.error('Ошибка при запросе тайла:', error);
                showOfflineTile(tile, done);
            });
    } else {
        showOfflineTile(tile, done);
    }

    return tile;
},

_update: function() {
    this._tileCache = {};
    L.TileLayer.prototype._update.call(this);
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
done(null, tile);
}

// Генерация URL для CartoDB Voyager
function getCartoDBTileUrl(coords) {
var zoom = coords.z;
var x = coords.x;
var y = coords.y;

// CartoDB Voyager URL pattern
var subdomain = 'abcd'[Math.abs(x + y) % 4];
return `https://${subdomain}.basemaps.cartocdn.com/rastertiles/voyager/${zoom}/${x}/${y}.png`;
}

// Функция для получения текущих границ карты
function getCurrentBounds() {
var bounds = map.getBounds();
return {
    north: bounds.getNorth(),
    south: bounds.getSouth(),
    east: bounds.getEast(),
    west: bounds.getWest()
};
}

// Функция для получения текущего zoom уровня
function getCurrentZoom() {
return map.getZoom();
}

// Отслеживание изменений карты для обновления границ
map.on('moveend', function() {
updateMapBounds();
});

map.on('zoomend', function() {
updateMapBounds();
});

function updateMapBounds() {
var bounds = getCurrentBounds();
var zoom = getCurrentZoom();
// Можно отправить данные обратно в Python при необходимости
console.log("Границы обновлены:", bounds, "Zoom:", zoom);
}

// Инициализация начальных границ
updateMapBounds();

// Инициализация WebChannel
function bindBridge(channel) {
    webChannelInstance = channel;
    setBridge(channel.objects.bridge);
    console.log("WebChannel инициализирован");
    if (typeof window.onBridgeReady === 'function') {
        window.onBridgeReady();
    }
    initMap();
}

function ensureWebChannel() {
    if (webChannelInstance && webChannelInstance.objects && webChannelInstance.objects.bridge) {
        bindBridge(webChannelInstance);
        return;
    }

    if (typeof qt !== 'undefined' && qt.webChannelTransport) {
        new QWebChannel(qt.webChannelTransport, bindBridge);
    } else {
        console.error("WebChannel не доступен");
        initMap();
    }
}

ensureWebChannel();

function initMap() {
if (mapInitialized) {
    return;
}
mapInitialized = true;

// По умолчанию запускаем в офлайн-режиме
switchToOfflineLayer();

// Инициализируем точки
initPoints();

// Запускаем мониторинг подключений
startConnectivityMonitoring();

// Инициализируем обработчики событий для файлов
initFileHandlers();
}

function initFileHandlers() {
    // Обработчики для открытия файлов и папок через делегирование
    document.addEventListener('click', function(event) {
        const target = event.target;

        // Обработка кнопки "Открыть"
        if (target.classList.contains('open-doc')) {
            const fileName = target.getAttribute('data-filename');
            if (fileName) {
                openFile(fileName);
            }
            event.preventDefault();
        }

        // Обработка кнопки "Показать в проводнике"
        if (target.classList.contains('open-folder')) {
            const fileName = target.getAttribute('data-filename');
            if (fileName) {
                openFileLocation(fileName);
            }
            event.preventDefault();
        }
    });
}

function startConnectivityMonitoring() {
// Первичная проверка
handleConnectivityChange();

// Реакция на системные события браузера
window.addEventListener('online', handleConnectivityChange);
window.addEventListener('offline', handleConnectivityChange);

// Периодические проверки доступности тайлов (каждые 15 секунд)
setInterval(handleConnectivityChange, 15000);
}

function handleConnectivityChange() {
checkInternetConnectivity().then(function(isOnline) {
    connectivityState.isOnline = isOnline;
    connectivityState.lastChecked = Date.now();

    if (isOnline) {
        switchToOnlineLayer();
    } else {
        switchToOfflineLayer();
    }
});
}

function checkInternetConnectivity() {
if (!navigator.onLine) {
    return Promise.resolve(false);
}

var controller = new AbortController();
var timeoutId = setTimeout(function() {
    controller.abort();
}, 4000);

// Пробуем получить заголовки базового тайла
var testUrl = cartoDBVoyager.online.url
    .replace('{s}', 'a')
    .replace('{z}', '0')
    .replace('{x}', '0')
    .replace('{y}', '0')
    .replace('{r}', '');

return fetch(testUrl, { method: 'HEAD', signal: controller.signal })
    .then(function(response) {
        clearTimeout(timeoutId);
        return response.ok;
    })
    .catch(function(error) {
        clearTimeout(timeoutId);
        console.warn('Не удалось проверить интернет-соединение:', error);
        return false;
    });
}

function switchToOfflineLayer() {
if (currentMode === 'offline' && currentLayer) {
    console.log("Уже в офлайн-режиме");
    updateOnlineStatus();
    return;
}

console.log("Переключение в офлайн-режим");

// Удаляем текущий слой
if (currentLayer) {
    map.removeLayer(currentLayer);
}

// Создаем офлайн-слой с CartoDB Voyager URL pattern
currentLayer = new OfflineTileLayer({
    attribution: 'CartoDB Voyager | Офлайн тайлы из кэша',
    minZoom: 0,
    maxZoom: 20
});

// Переопределяем метод получения URL для CartoDB
currentLayer.getTileUrl = function(coords) {
    return getCartoDBTileUrl(coords);
};

currentLayer.addTo(map);
currentMode = 'offline';
updateOnlineStatus();

// Уведомляем Python о переключении
if (getBridge()) {
    getBridge().switchToOfflineMode();
}

console.log("Успешно переключен в офлайн-режим");
}

function switchToOnlineLayer() {
if (currentMode === 'online') {
    console.log("Уже в онлайн-режиме");
    updateOnlineStatus();
    return;
}

// Проверяем доступность интернета на основе последней проверки
if (!connectivityState.isOnline) {
    console.warn("Отсутствует интернет-соединение для онлайн-режима");
    updateOnlineStatus();
    return;
}

console.log("Переключение в онлайн-режим");

// Удаляем текущий слой
if (currentLayer) {
    map.removeLayer(currentLayer);
}

// Создаем онлайн-слой CartoDB Voyager
currentLayer = L.tileLayer(
    cartoDBVoyager.online.url,
    cartoDBVoyager.online.options
);

currentLayer.addTo(map);
currentMode = 'online';
updateOnlineStatus();

// Уведомляем Python о переключении
if (getBridge()) {
    getBridge().switchToOnlineMode();
}

console.log("Успешно переключен в онлайн-режим");
}

function updateOnlineStatus() {
var statusElement = document.getElementById('offline-status');

// Обновляем на основе текущего режима
if (currentMode === 'online') {
    statusElement.innerHTML = '● CartoDB Voyager - Онлайн режим';
    statusElement.className = 'offline-status online';
} else {
    var offlineReason = connectivityState.lastChecked === 0
        ? 'Проверка соединения...'
        : (connectivityState.isOnline ? 'Принудительно выбран офлайн режим' : 'Нет подключения к интернету');
    statusElement.innerHTML = '○ CartoDB Voyager - Офлайн режим (' + offlineReason + ')';
    statusElement.className = 'offline-status offline';
}
}

// Инициализация точек
function initPoints() {
if (typeof initialMarkerData !== 'undefined' && initialMarkerData.length > 0) {
    initialMarkerData.forEach(function(point, index) {
        addMarker(
            point.lat,
            point.lng,
            point.name,
            point.id,
            point.deep,
            point.filters,
            point.debit,
            point.comments,
            point.color,
            point.fileName,
            point.fileNames || []
        );
    });
    initialMarkerData = [];

    updateNavTree();
    updateSelectedPointsList();
}
}

// Добавление маркера
function addMarker(lat, lng, name, id, deep, filters, debit, comments, color, fileName, fileNames) {
if (!color) color = '#4361ee';

// Создаем кастомную иконку с выбранным цветом
var markerIcon = L.divIcon({
    html: `<div style="background-color: ${color}; width: 12px; height: 12px; border-radius: 50%; border: 2px solid white; box-shadow: 0 0 0 3px ${color}, 0 0 10px rgba(0,0,0,0.5);"></div>`,
    className: 'custom-marker',
    iconSize: [15, 15],
    iconAnchor: [7, 7]
});

var marker = L.marker([lat, lng], {icon: markerIcon}).addTo(markers);

if (name) {
    // Добавляем количество файлов в popup
    var fileCount = fileNames ? fileNames.length : (fileName ? 1 : 0);
    var popupContent = `<strong>${name}</strong>`;
    if (fileCount > 0) {
        popupContent += `<br><small>Файлов: ${fileCount}</small>`;
    }
    marker.bindPopup(popupContent);
}

const tooltipParts = [];
if (name) {
    tooltipParts.push(`<strong>${escapeHtml(name)}</strong>`);
}
if (deep !== undefined && deep !== null && deep !== '') {
    tooltipParts.push(`Глубина: ${escapeHtml(String(deep))}`);
}
if (tooltipParts.length) {
    marker.bindTooltip(tooltipParts.join('<br>'), {
        direction: 'top',
        opacity: 0.95,
        sticky: true
    });
}

// Сохраняем данные маркера
var markerInfo = {
    id: id,
    lat: lat,
    lng: lng,
    name: name,
    marker: marker,
    deep: deep,
    filters: filters,
    debit: debit,
    comments: comments,
    color: color,
    fileName: fileName || null,
    fileNames: fileNames || [],
    visible: true
};

markerData.push(markerInfo);
markerIndex.set(id, markerInfo);

// Добавляем обработчик клика для показа информации
marker.on('click', function() {
    showPointInfo(markerInfo);
    toggleMarkerSelection(markerInfo.id);
});

updateNavTree();
return marker;
}

function updateMarkerData(updatedPoint) {
if (!updatedPoint || !updatedPoint.id) {
    return;
}

var marker = getMarkerById(updatedPoint.id);
if (!marker) {
    return;
}

marker.name = updatedPoint.name;
marker.deep = updatedPoint.deep;
marker.filters = updatedPoint.filters;
marker.debit = updatedPoint.debit;
marker.comments = updatedPoint.comments;
marker.color = updatedPoint.color || '#4361ee';
marker.fileNames = updatedPoint.fileNames || [];
marker.fileName = updatedPoint.fileName || null;
marker.lat = updatedPoint.lat !== undefined ? updatedPoint.lat : marker.lat;
marker.lng = updatedPoint.lng !== undefined ? updatedPoint.lng : marker.lng;

var markerIcon = L.divIcon({
    html: `<div style="background-color: ${marker.color}; width: 12px; height: 12px; border-radius: 50%; border: 2px solid white; box-shadow: 0 0 0 3px ${marker.color}, 0 0 10px rgba(0,0,0,0.5);"></div>`,
    className: 'custom-marker',
    iconSize: [15, 15],
    iconAnchor: [7, 7]
});

marker.marker.setIcon(markerIcon);
marker.marker.setLatLng([marker.lat, marker.lng]);

var fileCount = marker.fileNames ? marker.fileNames.length : (marker.fileName ? 1 : 0);
var popupContent = `<strong>${marker.name || ''}</strong>`;
if (fileCount > 0) {
    popupContent += `<br><small>Файлов: ${fileCount}</small>`;
}
marker.marker.bindPopup(popupContent);

const tooltipParts = [];
if (marker.name) {
    tooltipParts.push(`<strong>${escapeHtml(marker.name)}</strong>`);
}
if (marker.deep !== undefined && marker.deep !== null && marker.deep !== '') {
    tooltipParts.push(`Глубина: ${escapeHtml(String(marker.deep))}`);
}
if (tooltipParts.length) {
    marker.marker.bindTooltip(tooltipParts.join('<br>'), {
        direction: 'top',
        opacity: 0.95,
        sticky: true
    });
} else {
    marker.marker.unbindTooltip();
}

updateNavTree();
updateSelectedPointsList();

if (selectedMarkerIds.indexOf(marker.id) !== -1) {
    showPointInfo(marker);
}
}

function removeSelectedPoints() {
   selectedMarkerIds.forEach(markerId => {
    const marker = getMarkerById(markerId);
    if (marker) {
        var activeBridge = getBridge();
        if (activeBridge) {
            activeBridge.removePoint(marker.id);
        }
    }
   });
}

function updateNavTree() {
    if (navTreeScheduled) return;
    navTreeScheduled = true;
    requestAnimationFrame(renderNavTree);
}

function renderNavTree() {
    navTreeScheduled = false;
    const navTree = document.getElementById('nav-tree');

    // Очищаем дерево
    navTree.innerHTML = '';

    if (markerData.length === 0) {
        const emptyItem = document.createElement('li');
        emptyItem.textContent = 'Добавьте маркеры, чтобы увидеть элементы дерева';
        emptyItem.classList.add('empty');
        navTree.appendChild(emptyItem);
    } else {
        // Группируем точки по цвету
        const groupedMarkers = {};
        markerData.forEach(marker => {
            if (!groupedMarkers[marker.color]) {
                groupedMarkers[marker.color] = [];
            }
            groupedMarkers[marker.color].push(marker);
        });

        const fragment = document.createDocumentFragment();

        // Создаем группы для каждого цвета
        Object.keys(groupedMarkers).forEach(color => {
            const groupMarkers = groupedMarkers[color];

            // Создаем заголовок группы
            const groupHeader = document.createElement('div');
            groupHeader.className = 'group-header';

            // Добавляем счетчик файлов в заголовок группы
            const totalFiles = groupMarkers.reduce((sum, marker) => sum + (marker.fileNames ? marker.fileNames.length : 0), 0);

            groupHeader.innerHTML = `
            <div class="group-title">
                <span style="color: ${color}">●</span>
                <span>Цвет: ${color}</span>
                <span style="margin-left: 8px; color: #777; font-size: 12px;">
                    (${groupMarkers.length} точек, ${totalFiles} файлов)
                </span>
            </div>
            <div class="group-toggle">
                <button class="icon-btn toggle-group" data-color="${color}">
                    ▼
                </button>
                <button class="icon-btn toggle-group-visibility" data-color="${color}">
                    👁
                </button>
            </div>
        `;

        // Создаем контейнер для маркеров группы
        const groupContent = document.createElement('div');
        groupContent.className = 'group-content';
        groupContent.id = `group-${color.replace('#', '')}`;

        // Добавляем маркеры в группу
        groupMarkers.forEach(function(marker, index) {
            const listItem = document.createElement('li');
            if (selectedMarkerIds.includes(marker.id)) {
                listItem.classList.add('selected');
            }

            if (!marker.visible) {
                listItem.style.opacity = '0.5';
            }

            const colorBox = document.createElement('div');
            colorBox.classList.add('marker-color');
            colorBox.style.backgroundColor = marker.color;

            const markerInfo = document.createElement('div');
            markerInfo.classList.add('marker-info');

            // Добавляем счетчик файлов к названию точки
            const fileCount = marker.fileNames ? marker.fileNames.length : 0;
            markerInfo.innerHTML = `
                <span>${marker.name}</span>
                ${fileCount > 0 ? `<span class="file-count">${fileCount}</span>` : ''}
            `;
            markerInfo.title = marker.name + (fileCount > 0 ? ` (${fileCount} файлов)` : '');

            // Используем замыкание для правильной привязки маркера
            markerInfo.onclick = (function(marker) {
                return function() {
                    showPointInfo(marker);
                    toggleMarkerSelection(marker.id);
                    map.panTo(marker.marker.getLatLng());
                    marker.marker.openPopup();
                };
            })(marker);

            const visibilityBtn = document.createElement('button');
            visibilityBtn.className = 'icon-btn';
            visibilityBtn.innerHTML = marker.visible ? '👁' : '👁‍🗨';
            visibilityBtn.title = marker.visible ? 'Скрыть точку' : 'Показать точку';
            visibilityBtn.onclick = (function(marker) {
                return function(e) {
                    e.stopPropagation();
                    toggleMarkerVisibility(marker.id);
                };
            })(marker);

            const deleteBtn = document.createElement('button');
            deleteBtn.classList.add('delete-btn');
            deleteBtn.innerHTML = '🗑';
            deleteBtn.title = 'Удалить точку';
            deleteBtn.onclick = (function(markerId) {
                return function(e) {
                    e.stopPropagation();
                    var activeBridge = getBridge();
                    if (activeBridge) {
                        activeBridge.removePoint(markerId);
                    }
                };
            })(marker.id);

            listItem.appendChild(colorBox);
            listItem.appendChild(markerInfo);
            listItem.appendChild(visibilityBtn);
            listItem.appendChild(deleteBtn);

            groupContent.appendChild(listItem);
        });

        // Добавляем группу в общий фрагмент, чтобы уменьшить количество операций с DOM
        fragment.appendChild(groupHeader);
        fragment.appendChild(groupContent);

        // Добавляем обработчики для группы
        const toggleBtn = groupHeader.querySelector('.toggle-group');
        const visibilityBtn = groupHeader.querySelector('.toggle-group-visibility');

        toggleBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            const groupId = this.getAttribute('data-color');
            const content = document.getElementById(`group-${groupId.replace('#', '')}`);
            const icon = this;

            if (content.classList.contains('expanded')) {
                content.classList.remove('expanded');
                icon.innerHTML = '▼';
            } else {
                content.classList.add('expanded');
                icon.innerHTML = '▲';
            }
        });

        visibilityBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            const groupId = this.getAttribute('data-color');
            const groupMarkers = groupedMarkers[groupId];
            const allVisible = groupMarkers.every(m => m.visible);

            groupMarkers.forEach(marker => {
                marker.visible = !allVisible;
                setMarkerVisibility(marker.id, marker.visible);
            });

            updateNavTree();
        });

        // Обработчик для заголовка группы (альтернативный способ развернуть/свернуть)
        groupHeader.addEventListener('click', function(e) {
            if (!e.target.closest('.group-toggle')) {
                const groupId = color.replace('#', '');
                const content = document.getElementById(`group-${groupId}`);
                const icon = this.querySelector('.toggle-group');

                if (content.classList.contains('expanded')) {
                    content.classList.remove('expanded');
                    icon.innerHTML = '▼';
                } else {
                    content.classList.add('expanded');
                    icon.innerHTML = '▲';
                }
            }
        });
    });

        navTree.appendChild(fragment);
    }
}

function updateSelectedPointsList() {
    if (selectedListScheduled) return;
    selectedListScheduled = true;
    requestAnimationFrame(renderSelectedPointsList);
}

function renderSelectedPointsList() {
    selectedListScheduled = false;
    const selectedList = document.getElementById('selected-points-list');
    const fragment = document.createDocumentFragment();

    // Очищаем список
    selectedList.innerHTML = '';

    if (selectedMarkerIds.length === 0) {
        const emptyItem = document.createElement('div');
        emptyItem.textContent = 'Нет выбранных точек';
        emptyItem.classList.add('empty');
        selectedList.appendChild(emptyItem);
    } else {
        // Добавляем выбранные точки в список
        selectedMarkerIds.forEach(markerId => {
            const marker = getMarkerById(markerId);
            if (marker) {
                const listItem = document.createElement('div');
                listItem.className = 'selected-point-item';

                const pointName = document.createElement('div');
                pointName.className = 'selected-point-name';

                // Добавляем счетчик файлов к названию точки
                const fileCount = marker.fileNames ? marker.fileNames.length : 0;
                pointName.innerHTML = `
                    <span>${marker.name}</span>
                    ${fileCount > 0 ? `<span class="file-count">${fileCount}</span>` : ''}
                `;
                pointName.title = marker.name + (fileCount > 0 ? ` (${fileCount} файлов)` : '');

                const removeBtn = document.createElement('button');
                removeBtn.className = 'remove-selected-btn';
                removeBtn.innerHTML = '✗';
                removeBtn.title = 'Убрать из выбранных';
                removeBtn.onclick = (function(markerId) {
                    return function() {
                        toggleMarkerSelection(markerId);
                    };
                })(marker.id);

                 pointName.onclick = (function(marker) {
                    return function() {
                        map.panTo(marker.marker.getLatLng());
                        marker.marker.openPopup();
                    };
                })(marker);

                listItem.appendChild(pointName);
                listItem.appendChild(removeBtn);
                fragment.appendChild(listItem);
            }
        });

        selectedList.appendChild(fragment);
    }
}

function showPointInfo(marker) {
const pointInfo = document.getElementById('point-info');

// Создаем HTML для информации о файлах
let fileHtml = '';
const files = (marker.fileNames && marker.fileNames.length > 0)
    ? marker.fileNames
    : (marker.fileName ? [marker.fileName] : []);

if (files.length > 0) {
    const fileItemsHtml = files.map(fileName => {
        const safeName = escapeHtml(fileName);
        return `
            <div class="file-item">
                <span class="file-name" title="${safeName}">${safeName}</span>
                <div class="file-actions">
                    <button class="file-action open-doc" data-filename="${safeName}">Открыть</button>
                    <button class="file-action open-folder" data-filename="${safeName}">Показать в проводнике</button>
                </div>
            </div>
        `;
    }).join('');

    fileHtml = `
        <p><strong>Прикрепленные файлы (${files.length}):</strong></p>
        <div class="files-list">
            ${fileItemsHtml}
        </div>
    `;
} else {
    fileHtml = '<p><strong>Прикрепленные файлы:</strong> отсутствуют</p>';
}

pointInfo.innerHTML = `
    <p><strong>Название:</strong> ${marker.name}</p>
    <p><strong>Координаты:</strong> ${marker.lat.toFixed(6)}, ${marker.lng.toFixed(6)}</p>
    <p><strong>Глубина:</strong> ${marker.deep}</p>
    <p><strong>Фильтры:</strong> ${marker.filters}</p>
    <p><strong>Дебит:</strong> ${marker.debit}</p>
    <p><strong>Комментарии:</strong> ${marker.comments}</p>
    ${fileHtml}
    <p><strong>Цвет маркера:</strong> <span style="color:${marker.color}">${marker.color}</span></p>
`;
}

function openFile(fileName) {
const activeBridgeForOpen = getBridge();
if (activeBridgeForOpen && typeof activeBridgeForOpen.openFileInWord === 'function') {
    activeBridgeForOpen.openFileInWord(fileName);
} else {
    console.error("Функция открытия файла недоступна");
    alert("Не удалось открыть файл. Функция недоступна.");
}
}

function openFileLocation(fileName) {
const activeBridgeForReveal = getBridge();
if (activeBridgeForReveal && typeof activeBridgeForReveal.openFileLocation === 'function') {
    activeBridgeForReveal.openFileLocation(fileName);
} else {
    console.error("Функция открытия каталога недоступна");
    alert("Не удалось открыть расположение файла. Функция недоступна.");
}
}

// Убраны глобальные экспорты функций, так как теперь используем делегирование событий
// window.openFile = openFile;
// window.openFileLocation = openFileLocation;

function toggleMarkerSelection(markerId) {
const index = selectedMarkerIds.indexOf(markerId);
if (index === -1) {
    selectedMarkerIds.push(markerId);
} else {
    selectedMarkerIds.splice(index, 1);
}
updateNavTree();
updateSelectedPointsList();
}

function selectAllMarkers() {
selectedMarkerIds = markerData.map(marker => marker.id);
updateNavTree();
updateSelectedPointsList();
}

function deselectAllMarkers() {
selectedMarkerIds = [];
updateNavTree();
updateSelectedPointsList();
}

function setMarkerVisibility(markerId, visible) {
const markerInfo = getMarkerById(markerId);
if (markerInfo) {
    markerInfo.visible = visible;
    if (visible) {
        markerInfo.marker.addTo(map);
    } else {
        map.removeLayer(markerInfo.marker);
    }
}
}

function toggleMarkerVisibility(markerId) {
const markerInfo = getMarkerById(markerId);
if (markerInfo) {
    markerInfo.visible = !markerInfo.visible;
    setMarkerVisibility(markerId, markerInfo.visible);
    updateNavTree();
}
}

function hideAllMarkers() {
markerData.forEach(marker => {
    marker.visible = false;
    setMarkerVisibility(marker.id, false);
});
updateNavTree();
}

function showAllMarkers() {
markerData.forEach(marker => {
    marker.visible = true;
    setMarkerVisibility(marker.id, true);
});
updateNavTree();
}

function hideSelectedMarkers() {
selectedMarkerIds.forEach(id => {
    const markerInfo = getMarkerById(id);
    if (markerInfo) {
        markerInfo.visible = false;
        setMarkerVisibility(id, false);
    }
});
updateNavTree();
}

function showSelectedMarkers() {
selectedMarkerIds.forEach(id => {
    const markerInfo = getMarkerById(id);
    if (markerInfo) {
        markerInfo.visible = true;
        setMarkerVisibility(id, true);
    }
});
updateNavTree();
}

function changeMarkerColor(color) {
if (selectedMarkerIds.length === 0) {
    alert('Сначала выберите маркеры, нажав на них в списке или на карте');
    return;
}

// Обновляем только выбранные маркеры
selectedMarkerIds.forEach(function(markerId) {
    const markerInfo = getMarkerById(markerId);
    if (markerInfo) {
        markerInfo.color = color;

        // Создаем новую иконку с обновленным цветом
        var newIcon = L.divIcon({
            html: `<div style="background-color: ${color}; width: 12px; height: 12px; border-radius: 50%; border: 2px solid white; box-shadow: 0 0 0 3px ${color}, 0 0 10px rgba(0,0,0,0.5);"></div>`,
            className: 'custom-marker',
            iconSize: [15, 15],
            iconAnchor: [7, 7]
        });

        markerInfo.marker.setIcon(newIcon);
    }
});

// Добавляем в очередь обновлений
colorChangeQueue.push({color: color, markerIds: [...selectedMarkerIds]});

// Запускаем таймер для отправки изменений (дебаунсинг)
if (colorChangeTimer) clearTimeout(colorChangeTimer);
colorChangeTimer = setTimeout(sendColorUpdates, 1000);

updateNavTree();
}

function sendColorUpdates() {
var activeBridgeForColor = getBridge();
if (colorChangeQueue.length === 0 || !activeBridgeForColor) return;

// Создаем карту последних цветов для каждого маркера
const latestColors = {};
colorChangeQueue.forEach(change => {
    change.markerIds.forEach(id => {
        latestColors[id] = change.color;
    });
});

// Обновляем данные маркеров
markerData.forEach(marker => {
    if (latestColors[marker.id]) {
        marker.color = latestColors[marker.id];
    }
});

// Отправляем только необходимые данные
const dataToSend = markerData.map(marker => ({
    id: marker.id,
    lat: marker.lat,
    lng: marker.lng,
    name: marker.name,
    deep: marker.deep,
    filters: marker.filters,
    debit: marker.debit,
    comments: marker.comments,
    color: marker.color,
    fileName: marker.fileName,  // Для обратной совместимости
    fileNames: marker.fileNames  // Массив файлов
}));

activeBridgeForColor.changeColor(JSON.stringify(dataToSend));
colorChangeQueue = [];
}

function removeMarker(id) {
const index = markerData.findIndex(m => m.id === id);
if (index !== -1) {
    map.removeLayer(markerData[index].marker);
    markerData.splice(index, 1);
    markerIndex.delete(id);

    // Удаляем из выбранных, если есть
    const selectedIndex = selectedMarkerIds.indexOf(id);
    if (selectedIndex !== -1) {
        selectedMarkerIds.splice(selectedIndex, 1);
    }

    updateNavTree();
    updateSelectedPointsList();
    document.getElementById('point-info').innerHTML = 'Выберите точку на карте или в списке';
}
}

function enableClickHandler() {
map.on('click', function(e) {
    var activeBridge = getBridge();
    if (activeBridge) {
        activeBridge.addPoint(e.latlng.lat, e.latlng.lng);
    }
});
}

function disableClickHandler() {
map.off('click');
}

function searchPoints() {
hideAllMarkers()
const searchText = document.getElementById('search-input').value.toLowerCase().trim();
const resultsContainer = document.getElementById('search-results');

if (!searchText) {
    resultsContainer.style.display = 'none';
    return;
}

// Ищем точки только по названию
const results = markerData.filter(marker =>
    marker.name && marker.name.toLowerCase().includes(searchText)
);

// Отображаем результаты
if (results.length === 0) {
    resultsContainer.innerHTML = '<div class="search-result-item">Ничего не найдено</div>';
} else {
    resultsContainer.innerHTML = '';
    results.forEach(marker => {
        toggleMarkerVisibility(marker.id)
        const fileCount = marker.fileNames ? marker.fileNames.length : 0;
        const resultItem = document.createElement('div');
        resultItem.className = 'search-result-item';
        resultItem.innerHTML = `
            <div>${marker.name}</div>
            <small style="color: #666;">Файлов: ${fileCount}</small>
        `;

        // Добавляем обработчик клика для перехода к точке
        resultItem.addEventListener('click', function() {
            showPointInfo(marker);
            toggleMarkerSelection(marker.id);
            map.panTo(marker.marker.getLatLng());
            marker.marker.openPopup();

            // Скрываем результаты после выбора
            resultsContainer.style.display = 'none';
        });

        resultsContainer.appendChild(resultItem);
    });
}

resultsContainer.style.display = 'block';
}

// Обработчики событий для элементов управления цветом
document.getElementById('apply-color').addEventListener('click', function() {
const color = document.getElementById('marker-color').value;
changeMarkerColor(color);
});

// Делегирование событий для цветовых опций
document.querySelector('.color-options').addEventListener('click', function(e) {
const colorOption = e.target.closest('.color-option');
if (colorOption) {
    const color = colorOption.getAttribute('data-color');
    document.getElementById('marker-color').value = color;

    // Обновляем визуальное выделение
    document.querySelectorAll('.color-option').forEach(function(opt) {
        opt.classList.remove('selected');
    });
    colorOption.classList.add('selected');
}
});

document.getElementById('marker-color').addEventListener('change', function() {
const color = this.value;

// Обновляем визуальное выделение
document.querySelectorAll('.color-option').forEach(function(opt) {
    opt.classList.remove('selected');
    if (opt.getAttribute('data-color') === color) {
        opt.classList.add('selected');
    }
});
});

// Обработчики событий для поиска
document.getElementById('search-btn').addEventListener('click', searchPoints);

document.getElementById('search-input').addEventListener('keypress', function(e) {
if (e.key === 'Enter') {
    searchPoints();
}
});

// Обработчики для управления видимостью
document.getElementById('hide-all-btn').addEventListener('click', hideAllMarkers);
document.getElementById('show-all-btn').addEventListener('click', showAllMarkers);
document.getElementById('hide-selected-btn').addEventListener('click', hideSelectedMarkers);
document.getElementById('show-selected-btn').addEventListener('click', showSelectedMarkers);

// Обработчики для управления выделением
document.getElementById('select-all-btn').addEventListener('click', selectAllMarkers);
document.getElementById('deselect-all-btn').addEventListener('click', deselectAllMarkers);

// Обработчик для сворачивания/разворачивания навигационного дерева
document.getElementById('toggle-nav-tree').addEventListener('click', function() {
const content = document.getElementById('nav-tree-content');
const icon = this;

if (content.classList.contains('expanded')) {
    content.classList.remove('expanded');
    icon.innerHTML = '▼';
} else {
    content.classList.add('expanded');
    icon.innerHTML = '▲';
}
});

// Скрываем результаты поиска при клике вне области поиска
document.addEventListener('click', function(e) {
const searchContainer = document.querySelector('.search-container');
const searchResults = document.getElementById('search-results');

if (!searchContainer.contains(e.target)) {
    searchResults.style.display = 'none';
}
});

// Инициализация карты
initPoints();
