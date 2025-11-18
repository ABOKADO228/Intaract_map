import random
import string

from .data_manager import DataManager
from .paths import DATA_DIR


NAMES = [
    "Скважина",
    "Точка",
    "Замер",
    "Колонна",
    "Шахта",
]
COLORS = ["#4361ee", "#ff4757", "#2ed573", "#ffa502", "#a55eea", "#00d2d3"]


def random_text(prefix):
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=5))
    return f"{prefix} {suffix}"


def generate_points(count=2000):
    manager = DataManager(DATA_DIR)
    manager.clear_all_points()

    base_lat, base_lng = 59.93, 30.34
    for index in range(count):
        lat = base_lat + random.uniform(-0.6, 0.6)
        lng = base_lng + random.uniform(-0.6, 0.6)
        data = {
            "lat": lat,
            "lng": lng,
            "name": f"{random.choice(NAMES)} #{index + 1}",
            "deep": random_text("Глубина"),
            "filters": random_text("Фильтры"),
            "debit": random_text("Дебит"),
            "comments": random_text("Комментарий"),
            "color": random.choice(COLORS),
            "fileNames": [],
            "fileName": "",
        }
        manager.add_point(data)

    print(f"Создано {count} тестовых точек в базе данных: {manager.db_path}")


if __name__ == "__main__":
    generate_points()
