from pathlib import Path

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QPushButton, QTextEdit, QVBoxLayout, QWidget

from .base_tab import BaseTab


class LogsTab(BaseTab):
    def __init__(self, log_file: str = "operations.log", parent=None):
        super().__init__(parent)
        self.log_file = Path(log_file)

        self.text = QTextEdit()
        self.text.setReadOnly(True)
        self.refresh_btn = QPushButton("Обновить")

        layout = QVBoxLayout(self)
        layout.addWidget(self.text)
        layout.addWidget(self.refresh_btn)

        self.refresh_btn.clicked.connect(self.update_logs)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_logs)
        self.timer.start(5000)

        self.update_logs()

    def update_logs(self) -> None:
        if not self.log_file.exists():
            self.text.setPlainText("Лог-файл пока не создан")
            return
        content = self.log_file.read_text(encoding="utf-8", errors="replace").splitlines()
        self.text.setPlainText("\n".join(content[-100:]))
