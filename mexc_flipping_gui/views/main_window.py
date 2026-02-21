from __future__ import annotations

from datetime import datetime

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QMainWindow, QStatusBar, QTabWidget

from .api_tab import ApiTab
from .logs_tab import LogsTab
from .pairs_tab import PairsTab
from .stats_tab import StatsTab
from .strategy_tab import StrategyTab


class MainWindow(QMainWindow):
    def __init__(self, db_connection, fernet, pair_manager, config_manager, logger, encrypted_settings, trader=None):
        super().__init__()
        self.db_connection = db_connection
        self.fernet = fernet
        self.pair_manager = pair_manager
        self.config_manager = config_manager
        self.logger = logger
        self.encrypted_settings = encrypted_settings
        self.trader = trader
        self.worker = None

        self.setWindowTitle("MEXC Flipping Bot")
        self.resize(1100, 700)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

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

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.update_status("Готово")

        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self._update_clock)
        self.clock_timer.start(1000)

    def set_worker(self, worker) -> None:
        self.worker = worker
        if not self.worker:
            return
        self.worker.update_status.connect(self.update_status)
        self.worker.error_occurred.connect(self.show_error)
        self.worker.update_positions.connect(lambda _positions: self.stats_tab.refresh_data())
        self.worker.update_log.connect(lambda message: self.logger.info(message))
        self.worker.start()

    def update_status(self, message: str) -> None:
        self.status.showMessage(message)

    def show_error(self, message: str) -> None:
        self.status.showMessage(f"Ошибка: {message}", 5000)

    def _update_clock(self) -> None:
        now = datetime.now().strftime("%H:%M:%S")
        self.status.showMessage(f"{self.status.currentMessage().split(' | ')[0]} | {now}")

    def closeEvent(self, event) -> None:  # noqa: N802
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(5000)
        try:
            self.db_connection.close()
        except Exception:
            pass
        super().closeEvent(event)
