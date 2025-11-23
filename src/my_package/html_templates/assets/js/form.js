var dialogBridge = null;
var selectedFiles = [];
var existingFiles = [];
var initialFormData = window.initialFormData || null;

// Инициализация WebChannel
document.addEventListener("DOMContentLoaded", function() {
    if (typeof qt !== 'undefined') {
        new QWebChannel(qt.webChannelTransport, function(channel) {
            dialogBridge = channel.objects.dialogBridge;
            console.log("WebChannel для формы инициализирован");
        });
    }

    applyInitialData();
});

function applyInitialData() {
    if (!initialFormData) {
        return;
    }

    var title = document.getElementById('form-title');
    var submitBtn = document.getElementById('submit-btn');
    if (title) {
        title.textContent = '✏️ Редактирование точки';
    }
    if (submitBtn) {
        submitBtn.textContent = '💾 Сохранить изменения';
    }

    document.getElementById('name').value = initialFormData.name || '';
    document.getElementById('deep').value = initialFormData.deep || '';
    document.getElementById('filters').value = initialFormData.filters || '';
    document.getElementById('debit').value = initialFormData.debit || '';
    document.getElementById('comments').value = initialFormData.comments || '';

    if (initialFormData.color) {
        var colorInput = document.getElementById('color');
        colorInput.value = initialFormData.color;

        document.querySelectorAll('.color-option').forEach(function(option) {
            option.classList.toggle(
                'selected',
                option.getAttribute('data-color') === initialFormData.color
            );
        });
    }

    var incomingFiles = [];
    if (Array.isArray(initialFormData.fileNames) && initialFormData.fileNames.length > 0) {
        incomingFiles = initialFormData.fileNames.slice();
    } else if (initialFormData.fileName) {
        incomingFiles = [initialFormData.fileName];
    }

    existingFiles = incomingFiles;
    updateFileList();
}

// Обработчики цветовых опций
document.querySelectorAll('.color-option').forEach(function(option) {
    option.addEventListener('click', function() {
        document.querySelectorAll('.color-option').forEach(function(opt) {
            opt.classList.remove('selected');
        });
        this.classList.add('selected');
        document.getElementById('color').value = this.getAttribute('data-color');
    });
});

// Обработчики загрузки файлов
document.getElementById('fileUpload').addEventListener('click', function() {
    document.getElementById('fileInput').click();
});

document.getElementById('fileUpload').addEventListener('dragover', function(e) {
    e.preventDefault();
    this.style.borderColor = '#667eea';
    this.style.background = '#f0f4ff';
});

document.getElementById('fileUpload').addEventListener('dragleave', function(e) {
    e.preventDefault();
    this.style.borderColor = '#ddd';
    this.style.background = '';
});

document.getElementById('fileUpload').addEventListener('drop', function(e) {
    e.preventDefault();
    this.style.borderColor = '#ddd';
    this.style.background = '';
    handleFiles(e.dataTransfer.files);
});

document.getElementById('fileInput').addEventListener('change', function(e) {
    handleFiles(e.target.files);
});

function handleFiles(files) {
    for (let file of files) {
        const reader = new FileReader();
        reader.onload = function(e) {
            selectedFiles.push({
                fileName: file.name,
                fileSize: file.size,
                fileData: e.target.result
            });
            updateFileList();
        };
        reader.readAsDataURL(file);
    }
}

function updateFileList() {
    const fileList = document.getElementById('fileList');
    fileList.innerHTML = '';

    if (existingFiles.length > 0) {
        const header = document.createElement('div');
        header.className = 'file-section-header';
        header.textContent = 'Сохранённые файлы';
        fileList.appendChild(header);

        existingFiles.forEach(function(fileName) {
            const fileItem = document.createElement('div');
            fileItem.className = 'file-item existing';
            fileItem.innerHTML = `
                <span class="file-name">${fileName}</span>
                <span class="file-status">(уже прикреплен)</span>
            `;
            fileList.appendChild(fileItem);
        });
    }

    if (selectedFiles.length > 0) {
        const header = document.createElement('div');
        header.className = 'file-section-header';
        header.textContent = 'Новые файлы';
        fileList.appendChild(header);
    }

    selectedFiles.forEach(function(file, index) {
        const fileItem = document.createElement('div');
        fileItem.className = 'file-item';
        fileItem.innerHTML = `
            <span class="file-name">${file.fileName}</span>
            <button type="button" class="remove-file" data-index="${index}">
                ✕
            </button>
        `;
        fileList.appendChild(fileItem);
    });

    // Обработчики удаления файлов
    document.querySelectorAll('.remove-file').forEach(function(button) {
        button.addEventListener('click', function() {
            const index = parseInt(this.getAttribute('data-index'));
            selectedFiles.splice(index, 1);
            updateFileList();
        });
    });
}

// Обработчик отправки формы
document.getElementById('pointForm').addEventListener('submit', function(e) {
    e.preventDefault();

    if (!dialogBridge) {
        alert('Ошибка связи с приложением');
        return;
    }

    const formData = {
        name: document.getElementById('name').value,
        deep: document.getElementById('deep').value,
        filters: document.getElementById('filters').value,
        debit: document.getElementById('debit').value,
        comments: document.getElementById('comments').value,
        color: document.getElementById('color').value,
        files: selectedFiles,
        existingFileNames: existingFiles,
        id: initialFormData && initialFormData.id ? initialFormData.id : null
    };

    // Проверка обязательных полей
    if (!formData.name.trim()) {
        alert('Пожалуйста, введите название точки');
        return;
    }

    console.log('Отправка данных формы:', Object.keys(formData));
    dialogBridge.sendFormData(JSON.stringify(formData));
});

