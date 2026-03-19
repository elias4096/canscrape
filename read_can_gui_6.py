from __future__ import annotations

from dataclasses import dataclass
import sys
from typing import Dict, List, Optional, Tuple

import can
from can import BusABC, Message
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QBrush, QCloseEvent, QColor, Qt
from PySide6.QtWidgets import (
    QApplication,
    QDockWidget,
    QLabel,
    QMainWindow,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

#CAN_INTERFACE = "pcan"
#CAN_CHANNEL = "PCAN_USBBUS1"

CAN_INTERFACE= "slcan"
CAN_CHANNEL = "COM3"

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


class InspectorWidget(QWidget):
    def __init__(self, main_window: MainWindow):
        super().__init__()

        self.main_window = main_window

        layout = QVBoxLayout()

        self.elapsed_time_label = QLabel(f"Elapsed time: {main_window.initial_timestamp} s")
        layout.addWidget(self.elapsed_time_label)

        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear)
        layout.addWidget(self.clear_button)

        self.noise_filter_button = QPushButton("Start noise filter")
        self.noise_filter_button.clicked.connect(self.noise_filter)
        layout.addWidget(self.noise_filter_button)

        self.event_identifier_button = QPushButton("Start identifying event-bytes")
        self.event_identifier_button.clicked.connect(self.event_identifier)
        layout.addWidget(self.event_identifier_button)

        layout.addStretch()
        self.setLayout(layout)

    def clear(self) -> None:
        self.main_window.clear_noise_filter()
        self.main_window.clear_event_identifier()
        self.main_window.table.setRowCount(0)
        self.main_window.can_frames.clear()
        self.main_window.initial_timestamp = 0.0

    def noise_filter(self) -> None:
        self.main_window.running_noise_filter = not self.main_window.running_noise_filter
        if (self.main_window.running_noise_filter):
            self.main_window.clear_noise_filter()
            self.noise_filter_button.setText("Stop noise filter")
        else:
            self.noise_filter_button.setText("Start noise filter")

    def event_identifier(self) -> None:
        self.main_window.running_event_identifier = not self.main_window.running_event_identifier
        if (self.main_window.running_event_identifier):
            self.main_window.clear_event_identifier()
            self.event_identifier_button.setText("Stop identifying event-bytes")
        else:
            self.event_identifier_button.setText("Start identifying event-bytes")


@dataclass
class CANFrame:
    # program specific data
    row: int
    noise_filter: List[bool]
    event_identifier: List[bool]

    # typical can frame data
    time: float
    ext: bool
    cnt: int
    len: int
    data: bytearray


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("CAN Scrape")

        self.can_frames: Dict[int, CANFrame] = {}
        self.running_noise_filter: bool = False
        self.running_event_identifier: bool = False
        self.initial_timestamp: float = 0.0

        self.table: QTableWidget = QTableWidget(0, 14)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setHorizontalHeaderLabels(
            ["Time Stamp", "ID", "Extended", "Count", "Length", "D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8", "Bits (64)"]
        )
        self.table.resizeColumnsToContents()
        self.setCentralWidget(self.table)

        self.reader: CanReader = CanReader()
        self.reader.msg_signal.connect(self.update_table)
        self.reader.start()

        self.inspector = InspectorWidget(self)
        dock = QDockWidget("Inspector", self)
        dock.setWidget(self.inspector)

        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)


    def update_table(self, msg: Message) -> None:
        can_id: int = msg.arbitration_id

        if self.initial_timestamp <= 0.0:
            self.initial_timestamp = msg.timestamp

        self.inspector.elapsed_time_label.setText(f"Elapsed time: {msg.timestamp - self.initial_timestamp:.1f} s")

        # todo: optimize?
        if can_id in self.can_frames:
            row = self.can_frames[can_id].row
            count = self.can_frames[can_id].cnt + 1

            if self.running_noise_filter == True:
                for index, byte in enumerate(self.can_frames[can_id].data):
                    if msg.data[index] != byte:
                        self.can_frames[can_id].noise_filter[index] = True

            if self.running_event_identifier == True:
                for index, byte in enumerate(self.can_frames[can_id].data):
                    if msg.data[index] != byte:
                        self.can_frames[can_id].event_identifier[index] = True

            self.can_frames[can_id].time = msg.timestamp
            self.can_frames[can_id].ext = msg.is_extended_id
            self.can_frames[can_id].cnt = count
            self.can_frames[can_id].len = msg.dlc
            self.can_frames[can_id].data = msg.data
        else:
            row = self.table.rowCount()
            count = 1

            self.can_frames[can_id] = CANFrame(row, [False] * msg.dlc, [False] * msg.dlc, msg.timestamp, msg.is_extended_id, count, msg.dlc, msg.data)
            self.table.insertRow(row)

        self.table.setItem(row, 0, QTableWidgetItem(f"{msg.timestamp:.0f}"))
        self.table.setItem(row, 1, QTableWidgetItem(f"{can_id:03X}"))
        self.table.setItem(row, 2, QTableWidgetItem(str(msg.is_extended_id)))
        self.table.setItem(row, 3, QTableWidgetItem(str(count)))
        self.table.setItem(row, 4, QTableWidgetItem(str(msg.dlc)))

        for i in range(min(len(msg.data), 8)):
            item = QTableWidgetItem(f"{msg.data[i]:02X}")
            if self.can_frames[can_id].noise_filter[i] == True:
                item.setForeground(QBrush(QColor("red")))
            elif self.can_frames[can_id].event_identifier[i] == True:
                item.setForeground(QBrush(QColor("blue")))
            self.table.setItem(row, i + 5, item)

        # Build a 64-bit binary string
        bit_string = "".join(f"{byte:08b} " for byte in msg.data[:8])

        # Show in final column (column index 13)
        self.table.setItem(row, 13, QTableWidgetItem(bit_string))

    def closeEvent(self, event: QCloseEvent) -> None:
        self.reader.stop()
        self.reader.wait()
        super().closeEvent(event)

    def compare_data(self, old_data: bytearray, new_data: bytearray) -> List[bool]:
        changed_bits: List[bool] = [False] * 64

        for byte_index in range(8):  # 8 bytes
            xor_value = old_data[byte_index] ^ new_data[byte_index]

            for bit_index in range(8):  # 8 bits per byte
                absolute_bit = byte_index * 8 + (7 - bit_index)  # bit 7=MSB first
                changed_bits[absolute_bit] = bool(xor_value & (1 << bit_index))

        return changed_bits

    def clear_noise_filter(self) -> None:
        for can_frame in self.can_frames.values():
            can_frame.noise_filter = [False] * can_frame.len

    def clear_event_identifier(self) -> None:
        for can_frame in self.can_frames.values():
            can_frame.event_identifier = [False] * can_frame.len


if __name__ == "__main__":
    app: QApplication = QApplication(sys.argv)
    window = MainWindow()
    window.resize(960, 540)
    window.show()
    sys.exit(app.exec())