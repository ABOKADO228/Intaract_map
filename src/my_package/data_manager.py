import json
import os
import sqlite3
import uuid

from typing import List, Optional

from config import DATA_DIR, FILE_DIR


class DataManager:
    def __init__(self, data_path: Optional[str] = None):
        self.data_path = data_path or DATA_DIR
        self.data_file = os.path.join(self.data_path, "data.json")
        self.db_path = os.path.join(self.data_path, "data.db")
        self.current_data: List[dict] = []
        self.ensure_database()
        self.load_data()

    def ensure_database(self) -> None:
        os.makedirs(self.data_path, exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS points (
                id TEXT PRIMARY KEY,
                lat REAL,
                lng REAL,
                name TEXT,
                deep TEXT,
                filters TEXT,
                debit TEXT,
                comments TEXT,
                color TEXT,
                fileName TEXT,
                fileNames TEXT
            )
            """
        )

        conn.commit()

        cursor.execute("SELECT COUNT(*) FROM points")
        has_records = cursor.fetchone()[0] > 0

        if not has_records and os.path.exists(self.data_file):
            try:
                with open(self.data_file, "r", encoding="utf-8") as file:
                    legacy_data = json.load(file)

                for point in legacy_data:
                    self._insert_point(cursor, point)

                conn.commit()
                print("Данные из data.json перенесены в SQLite")
            except (json.JSONDecodeError, FileNotFoundError) as exc:
                print(f"Не удалось мигрировать данные из JSON: {exc}")

        conn.close()

    def _insert_point(self, cursor, point_data: dict) -> None:
        cursor.execute(
            """INSERT OR REPLACE INTO points (
                id, lat, lng, name, deep, filters, debit, comments, color, fileName, fileNames
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                point_data.get("id"),
                point_data.get("lat"),
                point_data.get("lng"),
                point_data.get("name"),
                point_data.get("deep"),
                point_data.get("filters"),
                point_data.get("debit"),
                point_data.get("comments"),
                point_data.get("color", "#4361ee"),
                point_data.get("fileName", ""),
                json.dumps(point_data.get("fileNames", []), ensure_ascii=False),
            ),
        )

    def load_data(self) -> None:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """SELECT id, lat, lng, name, deep, filters, debit, comments, color, fileName, fileNames FROM points"""
        )

        self.current_data = []
        for row in cursor.fetchall():
            try:
                file_names = json.loads(row[10]) if row[10] else []
            except json.JSONDecodeError:
                file_names = []

            point = {
                "id": row[0],
                "lat": row[1],
                "lng": row[2],
                "name": row[3],
                "deep": row[4],
                "filters": row[5],
                "debit": row[6],
                "comments": row[7],
                "color": row[8] or "#4361ee",
                "fileName": row[9] or "",
                "fileNames": file_names,
            }
            self.current_data.append(point)

        conn.close()

    def save_data(self) -> None:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM points")
        for point in self.current_data:
            if "id" not in point:
                point["id"] = str(uuid.uuid4())
            self._insert_point(cursor, point)

        conn.commit()
        conn.close()

    def add_point(self, point_data: dict) -> str:
        point_data["id"] = str(uuid.uuid4())
        self.current_data.append(point_data)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        self._insert_point(cursor, point_data)
        conn.commit()
        conn.close()
        return point_data["id"]

    def remove_point(self, point_id: str) -> None:
        point = next((p for p in self.current_data if p.get("id") == point_id), None)
        if not point:
            print(f"Точка с ID {point_id} не найдена.")
            return

        file_names = point.get("fileNames", [])
        if not file_names:
            single_file = point.get("fileName")
            if single_file and single_file not in [None, "Null"]:
                file_names = [single_file]

        for file_name in file_names:
            can_delete_file = all(
                file_name not in p.get("fileNames", [])
                and file_name != p.get("fileName")
                for p in self.current_data
                if p.get("id") != point_id
            )

            if can_delete_file:
                try:
                    file_path = os.path.join(FILE_DIR, file_name)
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        print(f"Файл '{file_path}' удален.")
                except OSError as exc:
                    print(f"Ошибка при удалении файла: {exc}")

        self.current_data = [p for p in self.current_data if p.get("id") != point_id]

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM points WHERE id = ?", (point_id,))
        conn.commit()
        conn.close()

    def clear_all_points(self) -> None:
        self.current_data = []
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM points")
        conn.commit()
        conn.close()

    def update_points(self, points_data: List[dict]) -> None:
        self.current_data = points_data
        self.save_data()

    def search_points(self, query: Optional[str]) -> List[dict]:
        if not query:
            return self.current_data

        query = query.lower()
        results: list[dict] = []
        for point in self.current_data:
            if (
                query in point.get("name", "").lower()
                or query in point.get("deep", "").lower()
                or query in point.get("filters", "").lower()
                or query in point.get("debit", "").lower()
                or query in point.get("comments", "").lower()
                or any(query in fname.lower() for fname in point.get("fileNames", []))
            ):
                results.append(point)

        return results
