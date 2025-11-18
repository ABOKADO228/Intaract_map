import base64
import binascii
import json
import os
import uuid

from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot


class DialogBridge(QObject):
    formDataSubmitted = pyqtSignal(dict)

    def __init__(self, file_dir, parent=None):
        super().__init__(parent)
        self.file_dir = file_dir

    @pyqtSlot(str)
    def sendFormData(self, json_data):
        try:
            data = json.loads(json_data)
            files_data = data.get("files", [])
            saved_file_names = []

            for file_item in files_data:
                file_data = file_item.get("fileData")
                file_name = file_item.get("fileName")
                if file_data:
                    try:
                        base64_data = file_data.split(",", 1)[1] if file_data.startswith("data:") else file_data
                        file_bytes = base64.b64decode(base64_data) if base64_data else b""

                        base_name, extension = os.path.splitext(file_name)
                        unique_name = f"{base_name}_{uuid.uuid4().hex[:8]}{extension}"

                        file_path = os.path.join(self.file_dir, unique_name)
                        with open(file_path, "wb") as file_handle:
                            file_handle.write(file_bytes)

                        saved_file_names.append(unique_name)

                    except (binascii.Error, Exception) as exc:
                        print(f"Ошибка обработки файла '{file_name}': {exc}")
                else:
                    print(f"Пропущен файл '{file_name}': отсутствуют данные")

            data["fileNames"] = saved_file_names
            self.formDataSubmitted.emit(data)

        except json.JSONDecodeError as exc:
            print(f"Ошибка parsing JSON: {exc}")
