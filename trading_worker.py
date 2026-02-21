from __future__ import annotations

import time

from PyQt5.QtCore import QThread, pyqtSignal


class TradingWorker(QThread):
    update_status = pyqtSignal(str)
    update_positions = pyqtSignal(list)
    update_log = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, trader, strategy, pair_manager, config_manager, logger):
        super().__init__()
        self.trader = trader
        self.strategy = strategy
        self.pair_manager = pair_manager
        self.config_manager = config_manager
        self.logger = logger
        self.running = False
        self._cooldown_until: dict[str, float] = {}
        self._last_position_state: dict[str, bool] = {}

    def start_trading(self) -> None:
        if self.running:
            return
        self.running = True
        self.logger.info("Trading started")
        self.update_status.emit("Trading started")

    def stop_trading(self) -> None:
        if not self.running:
            return
        self.running = False
        self.logger.info("Trading stopped")
        self.update_status.emit("Trading stopped")

    def run(self) -> None:
        self.start_trading()
        while self.running:
            try:
                if not self.trader:
                    self.update_status.emit("Нет API ключей: торговля недоступна")
                    self.stop_trading()
                    break

                active_symbols = self.pair_manager.get_active_pairs()
                now = time.time()

                for symbol in active_symbols:
                    if not self.running:
                        break

                    has_position = self.trader.has_open_position(symbol)
                    previous = self._last_position_state.get(symbol, False)
                    self._last_position_state[symbol] = has_position

                    if previous and not has_position:
                        self._apply_cooldown(symbol)

                    if has_position:
                        continue

                    if self._is_cooldown_active(symbol, now):
                        continue

                    result = self.strategy.generate_signal(symbol)
                    if not result.signal:
                        continue

                    if not self._passes_min_profit(symbol):
                        continue

                    order_id = self.trader.place_limit_order(symbol, result.signal)
                    if order_id:
                        self.update_log.emit(f"Signal {result.signal} on {symbol}: limit order created")

                positions = self.trader.exchange.fetch_positions() if self.trader else []
                self.update_positions.emit(positions)

                check_interval = int(self.config_manager.get("check_interval", 60))
                end_time = time.time() + max(1, check_interval)
                while self.running and time.time() < end_time:
                    self.msleep(200)
            except Exception as exc:
                message = f"Trading worker error: {exc}"
                self.logger.error(message)
                self.error_occurred.emit(message)
                if self.running:
                    self.msleep(1000)

        self.running = False

    def _passes_min_profit(self, symbol: str) -> bool:
        if not bool(self.config_manager.get("enable_min_profit_filter", False)):
            return True
        settings = self.pair_manager.get_pair_settings(symbol) or {}
        tp_percent = float(settings.get("tp_percent", 0.0))
        minimum = float(self.config_manager.get("min_profit_percent", 0.8))
        return tp_percent >= minimum

    def _apply_cooldown(self, symbol: str) -> None:
        if not bool(self.config_manager.get("enable_cooldown", False)):
            return
        cooldown_seconds = int(self.config_manager.get("cooldown_seconds", 60))
        self._cooldown_until[symbol] = time.time() + max(0, cooldown_seconds)

    def _is_cooldown_active(self, symbol: str, now: float) -> bool:
        if not bool(self.config_manager.get("enable_cooldown", False)):
            return False
        until = self._cooldown_until.get(symbol, 0)
        return now < until
