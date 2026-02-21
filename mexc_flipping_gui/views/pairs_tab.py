from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .base_tab import BaseTab


class PairDialog(QDialog):
    def __init__(self, parent=None, data: dict | None = None):
        super().__init__(parent)
        self.setWindowTitle("Пара")
        data = data or {}

        self.symbol = QLineEdit(data.get("symbol", ""))

        self.leverage = QSpinBox()
        self.leverage.setRange(1, 125)
        self.leverage.setValue(int(data.get("leverage", 10)))

        self.tp = QDoubleSpinBox()
        self.tp.setRange(0.1, 100)
        self.tp.setSingleStep(0.1)
        self.tp.setValue(float(data.get("tp_percent", 2.0)))

        self.sl = QDoubleSpinBox()
        self.sl.setRange(0.1, 100)
        self.sl.setSingleStep(0.1)
        self.sl.setValue(float(data.get("sl_percent", 1.0)))

        self.cancel_time = QSpinBox()
        self.cancel_time.setRange(0, 3600)
        self.cancel_time.setValue(int(data.get("cancel_time", 60)))

        self.enabled = QCheckBox("Включена")
        self.enabled.setChecked(bool(data.get("enabled", True)))

        form = QFormLayout()
        form.addRow("Символ", self.symbol)
        form.addRow("Плечо", self.leverage)
        form.addRow("TP %", self.tp)
        form.addRow("SL %", self.sl)
        form.addRow("Автоотмена, сек", self.cancel_time)
        form.addRow("", self.enabled)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def get_data(self) -> dict:
        return {
            "symbol": self.symbol.text().strip().upper(),
            "leverage": self.leverage.value(),
            "tp_percent": self.tp.value(),
            "sl_percent": self.sl.value(),
            "cancel_time": self.cancel_time.value(),
            "enabled": self.enabled.isChecked(),
        }


class PairsTab(BaseTab):
    HEADERS = ["Символ", "Плечо", "TP%", "SL%", "Автоотмена (сек)", "Статус", "Действия"]

    def __init__(self, pair_manager, logger, parent=None):
        super().__init__(parent)
        self.pair_manager = pair_manager
        self.logger = logger

        self.table = QTableWidget(0, len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)

        self.add_btn = QPushButton("Добавить пару")
        self.edit_btn = QPushButton("Редактировать")
        self.del_btn = QPushButton("Удалить")
        self.enable_btn = QPushButton("Включить")
        self.disable_btn = QPushButton("Выключить")

        self._build_ui()
        self.refresh_table()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(self.table)

        controls = QHBoxLayout()
        for btn in [self.add_btn, self.edit_btn, self.del_btn, self.enable_btn, self.disable_btn]:
            controls.addWidget(btn)
        controls.addStretch()
        layout.addLayout(controls)

        self.add_btn.clicked.connect(self.add_pair_dialog)
        self.edit_btn.clicked.connect(self.edit_pair)
        self.del_btn.clicked.connect(self.delete_pair)
        self.enable_btn.clicked.connect(lambda: self.toggle_pair(True))
        self.disable_btn.clicked.connect(lambda: self.toggle_pair(False))

    def refresh_table(self) -> None:
        self.pair_manager.load_pairs()
        pairs = list(self.pair_manager.pairs.values())
        self.table.setRowCount(len(pairs))
        for row, pair in enumerate(pairs):
            status = "Вкл" if pair["enabled"] else "Выкл"
            values = [
                pair["symbol"],
                str(pair["leverage"]),
                str(pair["tp_percent"]),
                str(pair["sl_percent"]),
                str(pair["cancel_time"]),
                status,
                "—",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() ^ Qt.ItemIsEditable)
                self.table.setItem(row, col, item)
        self.table.resizeColumnsToContents()

    def _selected_symbol(self) -> str | None:
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        return self.table.item(selected[0].row(), 0).text()

    def add_pair_dialog(self) -> None:
        dialog = PairDialog(self)
        if dialog.exec_() != QDialog.Accepted:
            return
        data = dialog.get_data()
        try:
            self.pair_manager.add_pair(**data)
            self.logger.info("Pair added from UI: %s", data["symbol"])
            self.refresh_table()
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка", str(exc))

    def edit_pair(self) -> None:
        symbol = self._selected_symbol()
        if not symbol:
            QMessageBox.warning(self, "Внимание", "Выберите пару")
            return
        current = self.pair_manager.get_pair_settings(symbol)
        dialog = PairDialog(self, current)
        if dialog.exec_() != QDialog.Accepted:
            return
        data = dialog.get_data()
        try:
            self.pair_manager.update_pair(symbol, **{k: v for k, v in data.items() if k != "symbol"})
            self.logger.info("Pair updated from UI: %s", symbol)
            self.refresh_table()
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка", str(exc))

    def delete_pair(self) -> None:
        symbol = self._selected_symbol()
        if not symbol:
            QMessageBox.warning(self, "Внимание", "Выберите пару")
            return
        self.pair_manager.remove_pair(symbol)
        self.logger.info("Pair deleted from UI: %s", symbol)
        self.refresh_table()

    def toggle_pair(self, enabled: bool) -> None:
        symbol = self._selected_symbol()
        if not symbol:
            QMessageBox.warning(self, "Внимание", "Выберите пару")
            return
        if enabled:
            self.pair_manager.enable_pair(symbol)
        else:
            self.pair_manager.disable_pair(symbol)
        self.refresh_table()
