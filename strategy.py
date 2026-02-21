from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class StrategySignal:
    signal: str | None
    context: dict[str, Any]


class FlippingStrategy:
    def __init__(self, exchange, config_manager, logger):
        self.exchange = exchange
        self.config_manager = config_manager
        self.logger = logger

    def fetch_ohlcv(self, symbol: str, limit: int = 300) -> list[list[float]]:
        return self.exchange.fetch_ohlcv(symbol, "1m", limit=limit)

    def generate_signal(self, symbol: str) -> StrategySignal:
        try:
            lookback = int(self.config_manager.get("lookback", 20))
            candles = self.fetch_ohlcv(symbol, limit=max(300, lookback + 210))
            if len(candles) < lookback + 210:
                return StrategySignal(None, {})

            current = candles[-1]
            prev_slice = candles[-(lookback + 1) : -1]
            highs = [c[2] for c in prev_slice]
            lows = [c[3] for c in prev_slice]
            volumes = [c[5] for c in prev_slice]

            current_close = float(current[4])
            current_volume = float(current[5])
            local_max = max(highs)
            local_min = min(lows)
            avg_volume = sum(volumes) / len(volumes)
            momentum = float(current[4] - candles[-4][4])

            closes = [float(c[4]) for c in candles]
            ema50 = self._ema(closes, 50)
            ema200 = self._ema(closes, 200)
            rsi14 = self._rsi(closes, 14)

            signal = None
            if current_close > local_max and momentum > 0:
                signal = "LONG"
            elif current_close < local_min and momentum < 0:
                signal = "SHORT"

            if not signal:
                return StrategySignal(None, self._ctx(current_close, avg_volume, current_volume, ema50, ema200, rsi14))

            if not self._passes_filters(signal, avg_volume, current_volume, ema50, ema200, rsi14):
                return StrategySignal(None, self._ctx(current_close, avg_volume, current_volume, ema50, ema200, rsi14))

            return StrategySignal(signal, self._ctx(current_close, avg_volume, current_volume, ema50, ema200, rsi14))
        except Exception as exc:
            self.logger.error("Strategy error for %s: %s", symbol, exc)
            return StrategySignal(None, {})

    def _passes_filters(self, side: str, avg_volume: float, current_volume: float, ema50: float, ema200: float, rsi14: float) -> bool:
        if bool(self.config_manager.get("enable_trend_filter", False)):
            if side == "LONG" and not (ema50 > ema200):
                return False
            if side == "SHORT" and not (ema50 < ema200):
                return False

        if bool(self.config_manager.get("enable_volume_filter", True)):
            vm = float(self.config_manager.get("volume_multiplier", 1.5))
            if not (current_volume > avg_volume * vm):
                return False

        if bool(self.config_manager.get("enable_rsi_filter", False)):
            rsi_long = float(self.config_manager.get("rsi_long_level", 35.0))
            rsi_short = float(self.config_manager.get("rsi_short_level", 65.0))
            if side == "LONG" and not (rsi14 < rsi_long):
                return False
            if side == "SHORT" and not (rsi14 > rsi_short):
                return False

        return True

    @staticmethod
    def _ema(values: list[float], period: int) -> float:
        k = 2 / (period + 1)
        ema = values[0]
        for v in values[1:]:
            ema = (v * k) + (ema * (1 - k))
        return ema

    @staticmethod
    def _rsi(values: list[float], period: int = 14) -> float:
        if len(values) < period + 1:
            return 50.0
        gains = 0.0
        losses = 0.0
        for i in range(-period, 0):
            delta = values[i] - values[i - 1]
            if delta >= 0:
                gains += delta
            else:
                losses -= delta
        if losses == 0:
            return 100.0
        rs = gains / losses
        return 100 - (100 / (1 + rs))

    @staticmethod
    def _ctx(current_close: float, avg_volume: float, current_volume: float, ema50: float, ema200: float, rsi14: float) -> dict[str, Any]:
        return {
            "current_close": current_close,
            "avg_volume": avg_volume,
            "current_volume": current_volume,
            "ema50": ema50,
            "ema200": ema200,
            "rsi14": rsi14,
        }
