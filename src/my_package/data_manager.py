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

    @staticmethod
    def _normalize_file_name(file_name: Optional[str]) -> Optional[str]:
        if not file_name:
            return None

        normalized = str(file_name).strip()
        if not normalized:
            return None

        if normalized.lower() in {"null", "none", "nan"}:
            return None

        return normalized

    def _clean_file_list(self, file_names: List[str]) -> List[str]:
        cleaned: List[str] = []
        for name in file_names or []:
            normalized = self._normalize_file_name(name)
            if normalized and normalized not in cleaned:
                cleaned.append(normalized)
        return cleaned

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
        attachments = self._clean_file_list(point_data.get("fileNames") or [])
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
                self._normalize_file_name(point_data.get("fileName")) or "",
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
            normalized = self._normalize_file_name(file_name)
            if not normalized:
                continue

            if point_id not in attachments_map:
                attachments_map[point_id] = []

            if normalized not in attachments_map[point_id]:
                attachments_map[point_id].append(normalized)
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
            fallback_file = self._normalize_file_name(row[9])
            if not file_names and fallback_file:
                file_names = [fallback_file]

            file_names = self._clean_file_list(file_names)
            primary_file = fallback_file or (file_names[0] if file_names else "")

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
                "fileName": primary_file,
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
            point["fileNames"] = self._clean_file_list(point.get("fileNames", []))
            point["fileName"] = (self._normalize_file_name(point.get("fileName")) or "")
            self._insert_point(cursor, point)

        conn.commit()
        conn.close()

    def add_point(self, point_data: dict) -> str:
        point_data["id"] = str(uuid.uuid4())
        point_data["fileNames"] = self._clean_file_list(point_data.get("fileNames", []))
        point_data["fileName"] = (self._normalize_file_name(point_data.get("fileName")) or "")
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

        file_names = self._clean_file_list(point.get("fileNames", []))
        if not file_names:
            single_file = self._normalize_file_name(point.get("fileName"))
            if single_file:
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

    def update_point(self, point_id: str, updated_data: dict) -> bool:
        point_index = next(
            (index for index, point in enumerate(self.current_data) if point.get("id") == point_id),
            None,
        )

        if point_index is None:
            print(f"Точка с ID {point_id} не найдена.")
            return False

        normalized_files = self._clean_file_list(updated_data.get("fileNames", []))
        normalized_primary = self._normalize_file_name(updated_data.get("fileName"))

        updated_point = {
            **self.current_data[point_index],
            **updated_data,
            "id": point_id,
            "fileNames": normalized_files,
            "fileName": normalized_primary or (normalized_files[0] if normalized_files else ""),
        }

        self.current_data[point_index] = updated_point

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        self._insert_point(cursor, updated_point)
        conn.commit()
        conn.close()
        return True

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
            fallback_file = self._normalize_file_name(row[9])
            if not file_names and fallback_file:
                file_names = [fallback_file]

            file_names = self._clean_file_list(file_names)
            primary_file = fallback_file or (file_names[0] if file_names else "")

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
                    "fileName": primary_file,
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
            normalized = self._normalize_file_name(file_name)
            if not normalized:
                continue

            if point_id not in attachments:
                attachments[point_id] = []

            if normalized not in attachments[point_id]:
                attachments[point_id].append(normalized)

        return attachments
