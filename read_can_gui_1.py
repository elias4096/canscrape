from __future__ import annotations

import sys
from typing import Dict, Optional, Tuple

import can
from can import BusABC, Message
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QTableWidget,
    QTableWidgetItem,
)

CAN_INTERFACE= "slcan"
CAN_CHANNEL = "COM9"
CAN_BITRATE = 500_000


class CanReader(QThread):
    msg_signal: Signal = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.running: bool = True

    def run(self) -> None:
        try:
            bus: BusABC = can.Bus(interface=CAN_INTERFACE, channel=CAN_CHANNEL, bitrate=CAN_BITRATE)
        except Exception as e:
            print("Failed to open CAN:", e)
            return

        while self.running:
            msg: Optional[Message] = bus.recv(0.5)
            if msg is not None:
                self.msg_signal.emit(msg)

    def stop(self) -> None:
        self.running = False


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("CAN Scrape")

        self.table: QTableWidget = QTableWidget(0, 13)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setHorizontalHeaderLabels(
            ["Time Stamp", "ID", "Extended", "Count", "Length", "D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8"]
        )
        self.table.resizeColumnsToContents()
        self.setCentralWidget(self.table)

        # Key: CAN ID, Value: (Row index, Count)
        self.rows_by_id: Dict[int, Tuple[int, int]] = {}

        self.reader: CanReader = CanReader()
        self.reader.msg_signal.connect(self.update_table)
        self.reader.start()

    def update_table(self, msg: Message) -> None:
        can_id: int = msg.arbitration_id

        if can_id in self.rows_by_id:
            row, count = self.rows_by_id[can_id]

            count += 1
            self.rows_by_id[can_id] = (row, count)
        else:
            row = self.table.rowCount()
            self.table.insertRow(row)

            count = 1
            self.rows_by_id[can_id] = (row, count)

        self.table.setItem(row, 0, QTableWidgetItem(f"{msg.timestamp:.0f}"))
        self.table.setItem(row, 1, QTableWidgetItem(f"{can_id:03X}"))
        self.table.setItem(row, 2, QTableWidgetItem(str(msg.is_extended_id)))
        self.table.setItem(row, 3, QTableWidgetItem(str(count)))
        self.table.setItem(row, 4, QTableWidgetItem(str(msg.dlc)))

        for i in range(min(len(msg.data), 8)):
            self.table.setItem(row, i + 5, QTableWidgetItem(f"{msg.data[i]:02X}"))

    def closeEvent(self, event: QCloseEvent) -> None:
        self.reader.stop()
        self.reader.wait()
        super().closeEvent(event)


if __name__ == "__main__":
    app: QApplication = QApplication(sys.argv)
    window = MainWindow()
    window.resize(960, 540)
    window.show()
    sys.exit(app.exec())