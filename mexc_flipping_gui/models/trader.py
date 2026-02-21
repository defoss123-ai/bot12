"""Trading module for MEXC futures using synchronous ccxt client."""

from __future__ import annotations

import threading
import time
import sqlite3
from typing import Any


class Trader:
    def __init__(self, exchange, pair_manager, db_connection: sqlite3.Connection, config_manager, logger) -> None:
        self.exchange = exchange
        self.pair_manager = pair_manager
        self.db_connection = db_connection
        self.config_manager = config_manager
        self.logger = logger

        self.active_orders: dict[str, dict[str, Any]] = {}
        self.position_cache: dict[str, dict[str, Any]] = {}

    def set_leverage(self, symbol: str, leverage: int) -> None:
        try:
            self.exchange.set_leverage(int(leverage), symbol)
            self.logger.info("Set leverage %sx for %s", leverage, symbol)
        except Exception as exc:
            self.logger.error("Failed to set leverage for %s: %s", symbol, exc)
            raise

    def get_balance_usdt(self) -> float:
        try:
            balance = self.exchange.fetch_balance()
            usdt_info = balance.get("USDT", {}) if isinstance(balance, dict) else {}
            total = usdt_info.get("total")
            if total is None:
                total = balance.get("total", {}).get("USDT", 0.0)
            return float(total or 0.0)
        except Exception as exc:
            self.logger.error("Failed to fetch USDT balance: %s", exc)
            return 0.0

    def calculate_quantity(self, symbol: str, side: str, leverage: int) -> float:
        risk_percent = float(self.config_manager.get("risk_per_trade", 5.0))
        balance = self.get_balance_usdt()
        ticker = self.exchange.fetch_ticker(symbol)
        current_price = float(ticker.get("last") or ticker.get("close") or 0)
        if current_price <= 0:
            raise ValueError(f"Invalid price for {symbol}")

        max_margin = balance * (risk_percent / 100)
        quantity = (max_margin * leverage) / current_price

        market = self.exchange.market(symbol)
        amount_precision = market.get("precision", {}).get("amount", 3)
        quantity = float(self.exchange.amount_to_precision(symbol, quantity)) if hasattr(self.exchange, "amount_to_precision") else round(quantity, amount_precision)
        self.logger.info("Calculated quantity for %s %s: %s", symbol, side, quantity)
        return max(quantity, 0.0)

    def place_limit_order(self, symbol: str, side: str, cancel_after: int | None = None) -> str | None:
        settings = self.pair_manager.get_pair_settings(symbol)
        if not settings:
            self.logger.warning("Pair settings missing for %s", symbol)
            return None

        leverage = int(settings["leverage"])
        cancel_after = int(cancel_after if cancel_after is not None else settings["cancel_time"])
        self.set_leverage(symbol, leverage)

        quantity = self.calculate_quantity(symbol, side, leverage)
        if quantity <= 0:
            self.logger.warning("Quantity is zero for %s", symbol)
            return None

        order_book = self.exchange.fetch_order_book(symbol)
        best_bid = float(order_book["bids"][0][0]) if order_book.get("bids") else 0.0
        best_ask = float(order_book["asks"][0][0]) if order_book.get("asks") else 0.0

        if side == "LONG":
            price = best_bid * 1.0002 if best_bid else float(self.exchange.fetch_ticker(symbol)["last"])
            order_side = "buy"
        else:
            price = best_ask * 0.9998 if best_ask else float(self.exchange.fetch_ticker(symbol)["last"])
            order_side = "sell"

        price = float(self.exchange.price_to_precision(symbol, price)) if hasattr(self.exchange, "price_to_precision") else price
        order = self.exchange.create_limit_order(symbol, order_side, quantity, price)
        order_id = order.get("id")

        self.active_orders[order_id] = {
            "symbol": symbol,
            "side": side,
            "amount": quantity,
            "price": price,
            "cancel_after": cancel_after,
        }

        with self.db_connection:
            self.db_connection.execute(
                """
                INSERT OR REPLACE INTO orders (id, symbol, side, type, price, amount, status, created_at, cancel_after)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
                """,
                (order_id, symbol, side, "limit", price, quantity, order.get("status", "open"), cancel_after),
            )

        self.logger.info("Placed %s limit order %s for %s", side, order_id, symbol)
        if cancel_after > 0:
            timer = threading.Timer(cancel_after, self.auto_cancel, args=(order_id, cancel_after))
            timer.daemon = True
            timer.start()

        return order_id

    def auto_cancel(self, order_id: str, delay: int) -> None:
        self.logger.info("Auto-cancel check for %s after %ss", order_id, delay)
        order_info = self.active_orders.get(order_id)
        if not order_info:
            return
        try:
            order = self.exchange.fetch_order(order_id, order_info["symbol"])
            if order.get("status") in {"open", "new"}:
                self.exchange.cancel_order(order_id, order_info["symbol"])
                self.logger.info("Order %s canceled by timer", order_id)
                with self.db_connection:
                    self.db_connection.execute("UPDATE orders SET status = ? WHERE id = ?", ("canceled", order_id))
        except Exception as exc:
            self.logger.error("Failed to auto-cancel order %s: %s", order_id, exc)

    def set_stop_loss_take_profit(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        quantity: float,
        sl_percent: float,
        tp_percent: float,
    ) -> None:
        if side == "LONG":
            sl_price = entry_price * (1 - sl_percent / 100)
            tp_price = entry_price * (1 + tp_percent / 100)
            close_side = "sell"
        else:
            sl_price = entry_price * (1 + sl_percent / 100)
            tp_price = entry_price * (1 - tp_percent / 100)
            close_side = "buy"

        sl_price = float(self.exchange.price_to_precision(symbol, sl_price))
        tp_price = float(self.exchange.price_to_precision(symbol, tp_price))

        self.exchange.create_order(
            symbol,
            "stop_market",
            close_side,
            quantity,
            None,
            {"stopPrice": sl_price, "reduceOnly": True},
        )
        self.exchange.create_order(
            symbol,
            "take_profit_limit",
            close_side,
            quantity,
            tp_price,
            {"stopPrice": tp_price, "reduceOnly": True},
        )
        self.logger.info("SL/TP orders placed for %s", symbol)

    def has_open_position(self, symbol: str) -> bool:
        try:
            positions = self.exchange.fetch_positions([symbol])
            for pos in positions:
                contracts = float(pos.get("contracts") or pos.get("positionAmt") or 0)
                if contracts != 0:
                    self.position_cache[symbol] = pos
                    return True
        except Exception as exc:
            self.logger.error("Failed to fetch position for %s: %s", symbol, exc)
        return False

    def check_orders_and_positions(self, sleep_s: int = 7, stop_event: threading.Event | None = None) -> None:
        while stop_event is None or not stop_event.is_set():
            try:
                for order_id, order_info in list(self.active_orders.items()):
                    order = self.exchange.fetch_order(order_id, order_info["symbol"])
                    status = order.get("status", "unknown")
                    with self.db_connection:
                        self.db_connection.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
                    if status in {"closed", "canceled", "rejected", "expired"}:
                        self.active_orders.pop(order_id, None)

                positions = self.exchange.fetch_positions()
                with self.db_connection:
                    for pos in positions:
                        symbol = pos.get("symbol")
                        contracts = float(pos.get("contracts") or pos.get("positionAmt") or 0)
                        if contracts == 0:
                            continue
                        side = "LONG" if contracts > 0 else "SHORT"
                        entry = float(pos.get("entryPrice") or pos.get("entry_price") or 0)
                        qty = abs(contracts)
                        self.position_cache[symbol] = pos
                        self.db_connection.execute(
                            """
                            INSERT INTO positions (symbol, side, entry_price, quantity, status, opened_at)
                            VALUES (?, ?, ?, ?, 'open', CURRENT_TIMESTAMP)
                            """,
                            (symbol, side, entry, qty),
                        )
            except Exception as exc:
                self.logger.error("Error in monitoring loop: %s", exc)
            time.sleep(sleep_s)

    def close_position(self, symbol: str) -> None:
        try:
            positions = self.exchange.fetch_positions([symbol])
            for pos in positions:
                contracts = float(pos.get("contracts") or pos.get("positionAmt") or 0)
                if contracts == 0:
                    continue
                side = "sell" if contracts > 0 else "buy"
                amount = abs(contracts)
                self.exchange.create_market_order(symbol, side, amount, params={"reduceOnly": True})
                with self.db_connection:
                    self.db_connection.execute(
                        "UPDATE positions SET status = 'closed', closed_at = CURRENT_TIMESTAMP WHERE symbol = ? AND status = 'open'",
                        (symbol,),
                    )
                self.logger.info("Position closed for %s", symbol)
                return
            self.logger.warning("No open position found for %s", symbol)
        except Exception as exc:
            self.logger.error("Failed to close position for %s: %s", symbol, exc)
