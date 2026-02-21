from PyQt5.QtWidgets import QWidget


class BaseTab(QWidget):
    def notify(self, text: str, timeout_ms: int = 3000) -> None:
        window = self.window()
        if hasattr(window, "statusBar"):
            window.statusBar().showMessage(text, timeout_ms)
