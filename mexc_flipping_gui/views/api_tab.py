from __future__ import annotations

from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .base_tab import BaseTab


class ConnectionCheckWorker(QThread):
    finished_check = pyqtSignal(bool, str)

    def __init__(self, api_key: str, api_secret: str) -> None:
        super().__init__()
        self.api_key = api_key
        self.api_secret = api_secret

    def run(self) -> None:
        try:
            import ccxt

            exchange = ccxt.mexc(
                {
                    "apiKey": self.api_key,
                    "secret": self.api_secret,
                    "options": {"defaultType": "swap", "unifiedAccount": True},
                    "enableRateLimit": True,
                }
            )
            exchange.fetch_balance()
            self.finished_check.emit(True, "Подключение успешно")
        except Exception as exc:
            self.finished_check.emit(False, f"Ошибка подключения: {exc}")


class ApiTab(BaseTab):
    keys_saved = pyqtSignal()

    def __init__(self, encrypted_settings, fernet, logger, parent=None):
        super().__init__(parent)
        self.encrypted_settings = encrypted_settings
        self.fernet = fernet
        self.logger = logger
        self.check_worker: ConnectionCheckWorker | None = None

        self.api_key_input = QLineEdit()
        self.api_secret_input = QLineEdit()
        self.api_secret_input.setEchoMode(QLineEdit.Password)

        self.check_button = QPushButton("Проверить подключение")
        self.save_button = QPushButton("Сохранить")
        self.result_label = QLabel("")

        self._build_ui()
        self._load_masked_keys()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.addRow("API Key", self.api_key_input)
        form.addRow("API Secret", self.api_secret_input)

        buttons = QHBoxLayout()
        buttons.addWidget(self.check_button)
        buttons.addWidget(self.save_button)

        layout.addLayout(form)
        layout.addLayout(buttons)
        layout.addWidget(self.result_label)
        layout.addStretch()

        self.check_button.clicked.connect(self.check_connection)
        self.save_button.clicked.connect(self.save_keys)

    def _load_masked_keys(self) -> None:
        api_key, api_secret = self.encrypted_settings.get_api_keys()
        if api_key:
            self.api_key_input.setPlaceholderText("*" * min(12, len(api_key)))
        if api_secret:
            self.api_secret_input.setPlaceholderText("*" * min(12, len(api_secret)))

    def check_connection(self) -> None:
        api_key = self.api_key_input.text().strip()
        api_secret = self.api_secret_input.text().strip()
        if not api_key or not api_secret:
            self._set_result(False, "Введите API key и secret")
            return

        self.check_button.setEnabled(False)
        self.check_worker = ConnectionCheckWorker(api_key, api_secret)
        self.check_worker.finished_check.connect(self._on_check_finished)
        self.check_worker.start()

    def _on_check_finished(self, success: bool, message: str) -> None:
        self.check_button.setEnabled(True)
        self._set_result(success, message)

    def _set_result(self, success: bool, message: str) -> None:
        color = "green" if success else "red"
        self.result_label.setStyleSheet(f"color: {color};")
        self.result_label.setText(message)

    def save_keys(self) -> None:
        api_key = self.api_key_input.text().strip()
        api_secret = self.api_secret_input.text().strip()
        if not api_key or not api_secret:
            self._set_result(False, "Нельзя сохранить пустые ключи")
            return
        try:
            self.encrypted_settings.set_api_keys(api_key, api_secret)
            self.logger.info("API keys saved from UI")
            self._set_result(True, "Ключи сохранены. Перезапустите приложение для активации трейдера.")
            self.keys_saved.emit()
        except Exception as exc:
            self.logger.error("Failed to save API keys: %s", exc)
            self._set_result(False, f"Ошибка сохранения: {exc}")
