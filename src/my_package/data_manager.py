import os
import sqlite3
import uuid

from typing import Dict, List, Optional

from config import DATA_DIR, FILE_DIR


class DataManager:
    def __init__(self, data_path: Optional[str] = None):
        self.data_path = data_path or DATA_DIR
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
                fileName TEXT
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS attachments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                point_id TEXT NOT NULL,
                file_name TEXT NOT NULL,
                FOREIGN KEY(point_id) REFERENCES points(id) ON DELETE CASCADE
            )
            """
        )

        conn.commit()
        conn.close()

    def _insert_point(self, cursor, point_data: dict) -> None:
        attachments = list(point_data.get("fileNames") or [])
        cursor.execute(
            """INSERT OR REPLACE INTO points (
                id, lat, lng, name, deep, filters, debit, comments, color, fileName
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
            ),
        )

        cursor.execute("DELETE FROM attachments WHERE point_id = ?", (point_data.get("id"),))
        for file_name in attachments:
            cursor.execute(
                "INSERT INTO attachments (point_id, file_name) VALUES (?, ?)",
                (point_data.get("id"), file_name),
            )

    def _fetch_attachments_map(self, cursor) -> Dict[str, List[str]]:
        attachments_map: Dict[str, List[str]] = {}
        cursor.execute("SELECT point_id, file_name FROM attachments")
        for point_id, file_name in cursor.fetchall():
            attachments_map.setdefault(point_id, []).append(file_name)
        return attachments_map

    def load_data(self) -> None:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """SELECT id, lat, lng, name, deep, filters, debit, comments, color, fileName FROM points"""
        )
        rows = cursor.fetchall()

        attachments_map = self._fetch_attachments_map(cursor)
        self.current_data = []
        for row in rows:
            file_names = attachments_map.get(row[0], [])
            if not file_names and row[9]:
                file_names = [row[9]]

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
        cursor.execute("DELETE FROM attachments")
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
        cursor.execute("DELETE FROM attachments WHERE point_id = ?", (point_id,))
        cursor.execute("DELETE FROM points WHERE id = ?", (point_id,))
        conn.commit()
        conn.close()

    def clear_all_points(self) -> None:
        self.current_data = []
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM attachments")
        cursor.execute("DELETE FROM points")
        conn.commit()
        conn.close()

    def update_points(self, points_data: List[dict]) -> None:
        self.current_data = points_data
        self.save_data()

    def search_points(self, query: Optional[str]) -> List[dict]:
        if not query:
            return self.current_data

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """SELECT id, lat, lng, name, deep, filters, debit, comments, color, fileName FROM points
            WHERE LOWER(name) LIKE ?""",
            (f"%{query.lower()}%",),
        )

        rows = cursor.fetchall()
        attachments_map = self._get_attachments_for_ids(cursor, [row[0] for row in rows])
        conn.close()

        results: List[dict] = []
        for row in rows:
            file_names = attachments_map.get(row[0], [])
            if not file_names and row[9]:
                file_names = [row[9]]

            results.append(
                {
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
            )

        return results

    def _get_attachments_for_ids(
        self, cursor, point_ids: List[str]
    ) -> Dict[str, List[str]]:
        attachments: Dict[str, List[str]] = {}
        if not point_ids:
            return attachments

        placeholders = ",".join("?" for _ in point_ids)
        cursor.execute(
            f"SELECT point_id, file_name FROM attachments WHERE point_id IN ({placeholders})",
            point_ids,
        )

        for point_id, file_name in cursor.fetchall():
            attachments.setdefault(point_id, []).append(file_name)

        return attachments
