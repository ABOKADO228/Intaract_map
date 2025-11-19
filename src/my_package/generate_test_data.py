import random
import uuid

from config import DATA_DIR
from data_manager import DataManager

TEST_LAT_RANGE = (59.6, 60.4)
TEST_LNG_RANGE = (29.8, 30.8)

FILTERS = [
    "Песчаный",
    "Гравийный",
    "Комбинированный",
    "Глиняный",
]

COMMENTS = [
    "Рабочая скважина",
    "Требуется очистка",
    "Не эксплуатируется",
    "Рекомендуется диагностика",
]


def build_point(index: int) -> dict:
    lat = round(random.uniform(*TEST_LAT_RANGE), 6)
    lng = round(random.uniform(*TEST_LNG_RANGE), 6)
    depth = f"{random.randint(30, 120)} м"
    debit = f"{random.uniform(5, 25):.1f} м³/ч"
    color = random.choice(["#4361ee", "#ff4757", "#2ed573", "#ffa502", "#a55eea", "#00d2d3"])

    return {
        "id": str(uuid.uuid4()),
        "lat": lat,
        "lng": lng,
        "name": f"Тестовая скважина #{index + 1}",
        "deep": depth,
        "filters": random.choice(FILTERS),
        "debit": debit,
        "comments": random.choice(COMMENTS),
        "color": color,
        "fileName": "",
        "fileNames": [],
    }


def generate_test_data(count: int = 2000) -> None:
    manager = DataManager(DATA_DIR)
    points = [build_point(i) for i in range(count)]
    manager.update_points(points)
    print(f"Сформировано {count} тестовых записей и сохранено в базе {manager.db_path}")


if __name__ == "__main__":
    generate_test_data()
