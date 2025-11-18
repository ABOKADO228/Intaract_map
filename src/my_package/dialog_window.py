import os

from PyQt5.QtCore import QUrl
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWidgets import QMainWindow, QMessageBox, QSizePolicy, QVBoxLayout, QWidget

from .dialog_bridge import DialogBridge
from .paths import RESOURCES_DIR, FILE_DIR


class DialogWindow(QMainWindow):
    def __init__(self, parent=None, resources_dir=RESOURCES_DIR, file_dir=FILE_DIR):
        super().__init__(parent)
        self.resources_dir = resources_dir
        self.file_dir = file_dir

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

        self.form.setHtml(html_template, QUrl.fromLocalFile(str(self.resources_dir) + "/"))

    def read_file(self, filename):
        try:
            file_path = os.path.join(self.resources_dir, filename)
            with open(file_path, "r", encoding="utf-8") as file_handle:
                return file_handle.read()
        except Exception as exc:
            print(f"Ошибка чтения файла {filename}: {exc}")
            return None

    def setup_web_channel(self):
        self.bridge = DialogBridge(self.file_dir, self)
        self.dataSubmitted = self.bridge.formDataSubmitted
        self.channel = QWebChannel()
        self.channel.registerObject("dialogBridge", self.bridge)
        self.form.page().setWebChannel(self.channel)
