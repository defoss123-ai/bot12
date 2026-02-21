from __future__ import annotations

from PyQt5.QtCore import QThread, pyqtSignal


class TradingWorker(QThread):
    update_status = pyqtSignal(str)
    update_positions = pyqtSignal(list)
    update_log = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, trader, signal_generator, pair_manager, config_manager, logger):
        super().__init__()
        self.trader = trader
        self.signal_generator = signal_generator
        self.pair_manager = pair_manager
        self.config_manager = config_manager
        self.logger = logger
        self._running = True

    def run(self) -> None:
        self.update_status.emit("Торговый поток запущен")
        while self._running:
            try:
                if not self.trader:
                    self.update_status.emit("Нет API ключей: торговля остановлена")
                    self.sleep(2)
                    continue

                active_symbols = self.pair_manager.get_active_pairs()
                for symbol in active_symbols:
                    if not self._running:
                        break
                    if self.trader.has_open_position(symbol):
                        continue

                    signal = self.signal_generator.generate_signal(symbol)
                    if signal:
                        self.trader.place_limit_order(symbol, signal)
                        self.update_log.emit(f"Signal {signal} on {symbol}: limit order created")

                positions = self.trader.exchange.fetch_positions() if self.trader else []
                self.update_positions.emit(positions)

                interval = int(self.config_manager.get("check_interval", 60))
                for _ in range(interval):
                    if not self._running:
                        break
                    self.sleep(1)
            except Exception as exc:
                message = f"Trading worker error: {exc}"
                self.logger.error(message)
                self.error_occurred.emit(message)
                self.sleep(2)

        self.update_status.emit("Торговый поток остановлен")

    def stop(self) -> None:
        self._running = False
