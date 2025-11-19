import base64
import base64
import binascii
import json
import os
import uuid

from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QUrl
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWidgets import QMainWindow, QMessageBox, QSizePolicy, QVBoxLayout, QWidget

from config import FILE_DIR, RESOURCES_DIR


class DialogBridge(QObject):
    formDataSubmitted = pyqtSignal(dict)

    @pyqtSlot(str)
    def sendFormData(self, json_data):
        try:
            data = json.loads(json_data)
            files_data = data.get("files", [])
            saved_file_names = []

            for file_item in files_data:
                file_data = file_item.get("fileData")
                file_name = file_item.get("fileName")
                if not file_data:
                    continue

                try:
                    if file_data == "data:":
                        base64_data = b""
                    else:
                        base64_data = file_data.split(",", 1)[1] if file_data.startswith("data:") else file_data
                    file_bytes = base64.b64decode(base64_data)

                    base_name, extension = os.path.splitext(file_name)
                    unique_name = f"{base_name}_{uuid.uuid4().hex[:8]}{extension}"
                    file_path = os.path.join(FILE_DIR, unique_name)
                    with open(file_path, "wb") as handle:
                        handle.write(file_bytes)

                    saved_file_names.append(unique_name)
                except (binascii.Error, Exception) as exc:
                    print(f"Ошибка обработки файла '{file_name}': {exc}")

            data["fileNames"] = saved_file_names
            self.formDataSubmitted.emit(data)

        except json.JSONDecodeError as exc:
            print(f"Ошибка parsing JSON: {exc}")


class DialogWindow(QMainWindow):
    dataSubmitted = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Point input window")
        self.resize(550, 950)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        self.form = QWebEngineView()
        self.form.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        layout.addWidget(self.form, 1)
        self.setup_web_channel()
        self.load_template()

    def load_template(self):
        html_template = self.read_file("form_template.html")

        if not html_template:
            QMessageBox.critical(self, "Ошибка", "Не удалось загрузить шаблон ввода")
            return

        self.form.setHtml(html_template, QUrl.fromLocalFile(str(RESOURCES_DIR) + "/"))

    def read_file(self, filename):
        try:
            file_path = os.path.join(RESOURCES_DIR, filename)
            with open(file_path, "r", encoding="utf-8") as handle:
                return handle.read()
        except Exception as exc:
            print(f"Ошибка чтения файла {filename}: {exc}")
            return None

    def setup_web_channel(self):
        self.bridge = DialogBridge(self)
        self.bridge.formDataSubmitted.connect(self.dataSubmitted)
        self.channel = QWebChannel()
        self.channel.registerObject("dialogBridge", self.bridge)
        self.form.page().setWebChannel(self.channel)
