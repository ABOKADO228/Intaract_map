import json
import os
from pathlib import Path
import random
from docx import Document
import string
import uuid

# Создаем директории, если они не существуют
base_dir = Path(__file__).parent
data_dir = base_dir / "data"
file_dir = data_dir / "files"
os.makedirs(file_dir, exist_ok=True)  # Важно: создаем папки

# Задаем границы для координат
lat_min, lat_max = 59.80, 60.10
lng_min, lng_max = 30.20, 30.80

# Списки для случайного выбора
names = ["Андреевка", "Озерки", "Лахта", "Пулково", "Парнас", "Шушары", "Ржевка", "Кудрово", "Девяткино", "Лисий Нос"]
deeps = [str(random.randint(10, 35)) for _ in range(1000)]
filters_list = [f"{random.randint(80, 150)}-{random.randint(80, 150)}" for _ in range(1000)]
debits = ["высокий", "средний", "слабый", "мощный", "нормальный", "нестабильный", "стабильный"]
comments_list = [
    "Чистая вода", "Требуется очистка", "Артезианский источник",
    "Высокое качество воды", "Необходим фильтр", "Пригодна для питья",
    "Красивое место", "Сезонные колебания", "Глубокий колодец"
]
colors = ["#ffa502", "#2ed573", "#ff7f50", "#1e90ff", "#ff6b81", "#ff4757", "#3742fa"]

data = []
all_symbols = string.ascii_letters + string.digits
length = 12

for _ in range(1000):
    # Генерация имени файла ПРАВИЛЬНО
    filename = 'file_' + ''.join(random.choice(all_symbols) for _ in range(length)) + '.docx'

    # Создание документа
    content = ''.join(random.choice(all_symbols) for _ in range(10000))
    doc = Document()
    doc.add_paragraph(content)

    # Генерация данных
    lat = random.uniform(lat_min, lat_max)
    lng = random.uniform(lng_min, lng_max)
    name = random.choice(names)
    deep = random.choice(deeps)
    filters = random.choice(filters_list)
    debit = random.choice(debits)
    comments = random.choice(comments_list)
    color = random.choice(colors)
    id = str(uuid.uuid4())

    # Сохранение файла
    doc.save(file_dir / filename)

    data.append({
        "lat": round(lat, 6),
        "lng": round(lng, 6),
        "name": name,
        "deep": deep,
        "filters": filters,
        "debit": debit,
        "fileName": filename,
        "comments": comments,
        "color": color,
        "id": id
    })

# Сохраняем в файл
with open(data_dir / 'data.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)