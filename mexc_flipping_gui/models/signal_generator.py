"""Signal generation logic for level breakout + volume strategy."""

from __future__ import annotations

from typing import Any


class SignalGenerator:
    def __init__(self, exchange, config_manager, logger) -> None:
        self.exchange = exchange
        self.config_manager = config_manager
        self.logger = logger

    def fetch_ohlcv(self, symbol: str, limit: int = 100) -> list[list[float]]:
        return self.exchange.fetch_ohlcv(symbol, "1m", limit=limit)

    def calculate_indicators(self, ohlcv: list[list[float]], lookback: int) -> dict[str, Any] | None:
        if len(ohlcv) < lookback + 4:
            return None

        current = ohlcv[-1]
        previous_slice = ohlcv[-(lookback + 1) : -1]
        highs = [candle[2] for candle in previous_slice]
        lows = [candle[3] for candle in previous_slice]
        volumes = [candle[5] for candle in previous_slice]

        momentum = current[4] - ohlcv[-4][4]

        return {
            "current_close": current[4],
            "current_volume": current[5],
            "local_max": max(highs),
            "local_min": min(lows),
            "avg_volume": sum(volumes) / len(volumes),
            "momentum": momentum,
        }

    def generate_signal(self, symbol: str) -> str | None:
        try:
            lookback = int(self.config_manager.get("lookback", 20))
            volume_multiplier = float(self.config_manager.get("volume_multiplier", 1.5))
            candles = self.fetch_ohlcv(symbol, limit=max(100, lookback + 10))
        except Exception as exc:
            self.logger.error("Failed to fetch OHLCV for %s: %s", symbol, exc)
            return None

        indicators = self.calculate_indicators(candles, lookback)
        if not indicators:
            self.logger.warning("Not enough OHLCV data for %s", symbol)
            return None

        is_volume_breakout = indicators["current_volume"] > indicators["avg_volume"] * volume_multiplier
        if not is_volume_breakout:
            return None

        if indicators["current_close"] > indicators["local_max"] and indicators["momentum"] > 0:
            return "LONG"
        if indicators["current_close"] < indicators["local_min"] and indicators["momentum"] < 0:
            return "SHORT"
        return None
