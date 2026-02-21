from __future__ import annotations

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .base_tab import BaseTab


class StatsTab(BaseTab):
    HEADERS = ["Символ", "Сторона", "Цена входа", "Количество", "P/L %", "P/L USDT"]

    def __init__(self, trader, pair_manager, logger, parent=None):
        super().__init__(parent)
        self.trader = trader
        self.pair_manager = pair_manager
        self.logger = logger

        self.balance_label = QLabel("Баланс USDT: -")
        self.refresh_btn = QPushButton("Обновить")
        self.close_btn = QPushButton("Закрыть выбранную позицию")

        self.table = QTableWidget(0, len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)

        self._build_ui()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_data)
        self.timer.start(5000)
        self.refresh_data()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(self.balance_label)
        top.addStretch()
        top.addWidget(self.refresh_btn)
        top.addWidget(self.close_btn)

        layout.addLayout(top)
        layout.addWidget(self.table)

        self.refresh_btn.clicked.connect(self.refresh_data)
        self.close_btn.clicked.connect(self.close_selected)

    def refresh_data(self) -> None:
        if not self.trader:
            self.balance_label.setText("Баланс USDT: трейдер не инициализирован")
            self.table.setRowCount(0)
            return
        try:
            balance = self.trader.get_balance_usdt()
            self.balance_label.setText(f"Баланс USDT: {balance:.2f}")

            positions = self.trader.exchange.fetch_positions()
            open_positions = [p for p in positions if abs(float(p.get("contracts") or p.get("positionAmt") or 0)) > 0]

            self.table.setRowCount(len(open_positions))
            for row, pos in enumerate(open_positions):
                symbol = pos.get("symbol", "")
                contracts = float(pos.get("contracts") or pos.get("positionAmt") or 0)
                side = "LONG" if contracts > 0 else "SHORT"
                entry = float(pos.get("entryPrice") or pos.get("entry_price") or 0)
                qty = abs(contracts)
                percentage = float(pos.get("percentage") or 0)
                pnl = float(pos.get("unrealizedPnl") or pos.get("unrealizedPnlValue") or 0)

                row_values = [symbol, side, f"{entry:.6f}", f"{qty:.6f}", f"{percentage:.2f}", f"{pnl:.4f}"]
                for col, value in enumerate(row_values):
                    self.table.setItem(row, col, QTableWidgetItem(value))
            self.table.resizeColumnsToContents()
        except Exception as exc:
            self.logger.error("Failed to refresh stats: %s", exc)

    def close_selected(self) -> None:
        if not self.trader:
            return
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            QMessageBox.warning(self, "Внимание", "Выберите позицию")
            return
        symbol = self.table.item(selected[0].row(), 0).text()
        self.trader.close_position(symbol)
        self.refresh_data()
