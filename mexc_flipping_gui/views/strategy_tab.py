from PyQt5.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .base_tab import BaseTab


class StrategyTab(BaseTab):
    def __init__(self, config_manager, logger, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.logger = logger

        self.lookback = QSpinBox()
        self.lookback.setRange(10, 100)

        self.volume_multiplier = QDoubleSpinBox()
        self.volume_multiplier.setRange(1.0, 5.0)
        self.volume_multiplier.setSingleStep(0.1)

        self.check_interval = QSpinBox()
        self.check_interval.setRange(10, 3600)

        self.risk_per_trade = QDoubleSpinBox()
        self.risk_per_trade.setRange(0.1, 50.0)
        self.risk_per_trade.setSingleStep(0.1)

        self.save_btn = QPushButton("Сохранить")
        self._build_ui()
        self.load_values()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.addRow("Lookback", self.lookback)
        form.addRow("Volume multiplier", self.volume_multiplier)
        form.addRow("Интервал проверки (сек)", self.check_interval)
        form.addRow("Риск на сделку (%)", self.risk_per_trade)
        layout.addLayout(form)
        layout.addWidget(self.save_btn)
        layout.addStretch()

        self.save_btn.clicked.connect(self.save_values)

    def load_values(self) -> None:
        self.lookback.setValue(int(self.config_manager.get("lookback", 20)))
        self.volume_multiplier.setValue(float(self.config_manager.get("volume_multiplier", 1.5)))
        self.check_interval.setValue(int(self.config_manager.get("check_interval", 60)))
        self.risk_per_trade.setValue(float(self.config_manager.get("risk_per_trade", 5.0)))

    def save_values(self) -> None:
        try:
            self.config_manager.set("lookback", self.lookback.value())
            self.config_manager.set("volume_multiplier", self.volume_multiplier.value())
            self.config_manager.set("check_interval", self.check_interval.value())
            self.config_manager.set("risk_per_trade", self.risk_per_trade.value())
            self.logger.info("Strategy settings updated from UI")
            QMessageBox.information(self, "Успех", "Настройки сохранены")
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка", str(exc))
