from __future__ import annotations

from datetime import datetime

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from mexc_flipping_gui.views.api_tab import ApiTab
from mexc_flipping_gui.views.logs_tab import LogsTab
from mexc_flipping_gui.views.pairs_tab import PairsTab
from mexc_flipping_gui.views.stats_tab import StatsTab
from mexc_flipping_gui.views.strategy_tab import StrategyTab
from trading_worker import TradingWorker


class MainWindow(QMainWindow):
    def __init__(self, db_connection, fernet, pair_manager, config_manager, logger, encrypted_settings, trader=None, strategy=None):
        super().__init__()
        self.db_connection = db_connection
        self.fernet = fernet
        self.pair_manager = pair_manager
        self.config_manager = config_manager
        self.logger = logger
        self.encrypted_settings = encrypted_settings
        self.trader = trader
        self.strategy = strategy
        self.worker: TradingWorker | None = None

        self.setWindowTitle("MEXC Flipping Bot")
        self.resize(1150, 760)

        self.tabs = QTabWidget()
        self.api_tab = ApiTab(self.encrypted_settings, self.fernet, self.logger)
        self.pairs_tab = PairsTab(self.pair_manager, self.logger)
        self.strategy_tab = StrategyTab(self.config_manager, self.logger)
        self.stats_tab = StatsTab(self.trader, self.pair_manager, self.logger)
        self.logs_tab = LogsTab()

        self.tabs.addTab(self.api_tab, "API")
        self.tabs.addTab(self.pairs_tab, "Пары")
        self.tabs.addTab(self.strategy_tab, "Стратегия")
        self.tabs.addTab(self.stats_tab, "Статистика")
        self.tabs.addTab(self.logs_tab, "Логи")

        self.start_button = QPushButton("Start Trading")
        self.stop_button = QPushButton("Stop Trading")
        self.stop_button.setEnabled(False)
        self.save_filters_button = QPushButton("Save Filter Settings")

        controls = QHBoxLayout()
        controls.addWidget(self.start_button)
        controls.addWidget(self.stop_button)
        controls.addStretch()

        self.filters_group = self._build_filters_group()

        central_layout = QVBoxLayout()
        central_layout.addLayout(controls)
        central_layout.addWidget(self.filters_group)
        central_layout.addWidget(self.tabs)
        central_layout.addWidget(self.save_filters_button)

        central_widget = QWidget()
        central_widget.setLayout(central_layout)
        self.setCentralWidget(central_widget)

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.update_status("Готово")

        self.start_button.clicked.connect(self.start_trading)
        self.stop_button.clicked.connect(self.stop_trading)
        self.save_filters_button.clicked.connect(self.save_filter_settings)

        self._load_filter_settings()

        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self._update_clock)
        self.clock_timer.start(1000)

    def _build_filters_group(self) -> QGroupBox:
        group = QGroupBox("Flipping Strategy Filters")
        form = QFormLayout(group)

        self.enable_trend_filter = QCheckBox("Enable Trend Filter")

        self.enable_volume_filter = QCheckBox("Enable Volume Filter")
        self.volume_multiplier = QDoubleSpinBox()
        self.volume_multiplier.setRange(1.0, 10.0)
        self.volume_multiplier.setSingleStep(0.1)

        self.enable_rsi_filter = QCheckBox("Enable RSI Filter")
        self.rsi_long_level = QDoubleSpinBox()
        self.rsi_long_level.setRange(1.0, 99.0)
        self.rsi_long_level.setSingleStep(1.0)
        self.rsi_short_level = QDoubleSpinBox()
        self.rsi_short_level.setRange(1.0, 99.0)
        self.rsi_short_level.setSingleStep(1.0)

        self.enable_min_profit_filter = QCheckBox("Enable Min Profit Filter")
        self.min_profit_percent = QDoubleSpinBox()
        self.min_profit_percent.setRange(0.1, 100.0)
        self.min_profit_percent.setSingleStep(0.1)

        self.enable_cooldown = QCheckBox("Enable Cooldown")
        self.cooldown_seconds = QSpinBox()
        self.cooldown_seconds.setRange(0, 86400)

        form.addRow(self.enable_trend_filter)
        form.addRow(self.enable_volume_filter)
        form.addRow("Volume multiplier", self.volume_multiplier)
        form.addRow(self.enable_rsi_filter)
        form.addRow("RSI Long Level", self.rsi_long_level)
        form.addRow("RSI Short Level", self.rsi_short_level)
        form.addRow(self.enable_min_profit_filter)
        form.addRow("Min Profit %", self.min_profit_percent)
        form.addRow(self.enable_cooldown)
        form.addRow("Cooldown seconds", self.cooldown_seconds)

        return group

    def _load_filter_settings(self) -> None:
        self.enable_trend_filter.setChecked(bool(self.config_manager.get("enable_trend_filter", False)))
        self.enable_volume_filter.setChecked(bool(self.config_manager.get("enable_volume_filter", True)))
        self.volume_multiplier.setValue(float(self.config_manager.get("volume_multiplier", 1.5)))
        self.enable_rsi_filter.setChecked(bool(self.config_manager.get("enable_rsi_filter", False)))
        self.rsi_long_level.setValue(float(self.config_manager.get("rsi_long_level", 35.0)))
        self.rsi_short_level.setValue(float(self.config_manager.get("rsi_short_level", 65.0)))
        self.enable_min_profit_filter.setChecked(bool(self.config_manager.get("enable_min_profit_filter", False)))
        self.min_profit_percent.setValue(float(self.config_manager.get("min_profit_percent", 0.8)))
        self.enable_cooldown.setChecked(bool(self.config_manager.get("enable_cooldown", False)))
        self.cooldown_seconds.setValue(int(self.config_manager.get("cooldown_seconds", 60)))

    def save_filter_settings(self) -> None:
        try:
            self.config_manager.set("enable_trend_filter", self.enable_trend_filter.isChecked())
            self.config_manager.set("enable_volume_filter", self.enable_volume_filter.isChecked())
            self.config_manager.set("volume_multiplier", self.volume_multiplier.value())
            self.config_manager.set("enable_rsi_filter", self.enable_rsi_filter.isChecked())
            self.config_manager.set("rsi_long_level", self.rsi_long_level.value())
            self.config_manager.set("rsi_short_level", self.rsi_short_level.value())
            self.config_manager.set("enable_min_profit_filter", self.enable_min_profit_filter.isChecked())
            self.config_manager.set("min_profit_percent", self.min_profit_percent.value())
            self.config_manager.set("enable_cooldown", self.enable_cooldown.isChecked())
            self.config_manager.set("cooldown_seconds", self.cooldown_seconds.value())
            QMessageBox.information(self, "Success", "Filter settings saved")
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def _connect_worker_signals(self, worker: TradingWorker) -> None:
        worker.update_status.connect(self.update_status)
        worker.error_occurred.connect(self.show_error)
        worker.update_positions.connect(lambda _positions: self.stats_tab.refresh_data())
        worker.update_log.connect(lambda message: self.logger.info(message))
        worker.finished.connect(self._on_worker_finished)

    def start_trading(self) -> None:
        if not self.trader or not self.strategy:
            self.update_status("Сначала сохраните API ключи и перезапустите приложение")
            return

        if self.worker and self.worker.isRunning() and self.worker.running:
            return

        if self.worker is None or self.worker.isFinished():
            self.worker = TradingWorker(
                trader=self.trader,
                strategy=self.strategy,
                pair_manager=self.pair_manager,
                config_manager=self.config_manager,
                logger=self.logger,
            )
            self._connect_worker_signals(self.worker)

        if not self.worker.isRunning():
            self.worker.start()

        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)

    def stop_trading(self) -> None:
        if not self.worker:
            return

        self.worker.stop_trading()
        if self.worker.isRunning():
            self.worker.wait(3000)

        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    def _on_worker_finished(self) -> None:
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    def update_status(self, message: str) -> None:
        self.status.showMessage(message)

    def show_error(self, message: str) -> None:
        self.status.showMessage(f"Ошибка: {message}", 5000)

    def _update_clock(self) -> None:
        now = datetime.now().strftime("%H:%M:%S")
        base = self.status.currentMessage().split(" | ")[0] if self.status.currentMessage() else "Готово"
        self.status.showMessage(f"{base} | {now}")

    def closeEvent(self, event) -> None:  # noqa: N802
        self.stop_trading()
        try:
            self.db_connection.close()
        except Exception:
            pass
        super().closeEvent(event)
