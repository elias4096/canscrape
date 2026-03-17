from __future__ import annotations

from dataclasses import dataclass
import sys
from typing import Dict, List, Optional, Tuple

import can
from can import BusABC, Message
from PySide6.QtCore import QThread, Signal, QRect, Qt
from PySide6.QtGui import QBrush, QCloseEvent, QColor, QFont, QColor, QPen, Qt
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
    QCheckBox,
    QStyledItemDelegate,
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


class BitsDelegate(QStyledItemDelegate):
    def __init__(self, window):
        super().__init__()
        self.w = window
        self.red = QColor(200, 0, 0)
        self.blue = QColor(0, 80, 200)
        self.black = QColor(0, 0, 0)

    def paint(self, painter, option, index):
        painter.save()
        painter.fillRect(option.rect, option.backgroundBrush)

        col = index.column()
        byte_idx = col - 13
        row = index.row()

        # Hämta CAN ID (kolumn 1)
        id_item = index.model().index(row, 1)
        id_hex = id_item.data()
        if not id_hex:
            painter.restore()
            return

        can_id = int(id_hex, 16)
        frame = self.w.can_frames.get(can_id)
        if frame is None:
            painter.restore()
            return

        text = index.data() or "00000000"

        r = option.rect.adjusted(4, 0, -4, 0)
        w = r.width() / 8

        for i in range(8):
            abs_bit = byte_idx * 8 + (7 - i)
            ch = text[i]

            if frame.noise_bits[abs_bit]:
                pen = QPen(self.red)
            elif frame.event_bits[abs_bit]:
                pen = QPen(self.blue)
            else:
                pen = QPen(self.black)

            painter.setPen(pen)
            painter.drawText(
                r.left() + i * w,
                r.top(),
                w,
                r.height(),
                Qt.AlignCenter,
                ch
            )

        painter.restore()

class InspectorWidget(QWidget):
    def __init__(self, main_window: MainWindow):
        super().__init__()

        self.main_window = main_window

        layout = QVBoxLayout()

        # Include bytes/bits (oförändrat)
        self.include_bytes = QCheckBox("Include bytes")
        self.include_bits = QCheckBox("Include bits")
        self.include_bytes.setChecked(True)
        self.include_bits.setChecked(False)
        self.include_bytes.toggled.connect(lambda _: self._on_include_toggled(self.include_bytes))
        self.include_bits.toggled.connect(lambda _: self._on_include_toggled(self.include_bits))
        self.include_bytes.toggled.connect(self.main_window.update_column_visibility)
        self.include_bits.toggled.connect(self.main_window.update_column_visibility)
        layout.addWidget(self.include_bytes)
        layout.addWidget(self.include_bits)

        self.elapsed_time_label = QLabel(f"Elapsed time: {main_window.initial_timestamp} s")
        layout.addWidget(self.elapsed_time_label)

        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear)
        layout.addWidget(self.clear_button)

        # Bytes-kontroller (befintliga)
        self.noise_filter_button = QPushButton("Start noise filter (bytes)")
        self.noise_filter_button.clicked.connect(self.noise_filter)
        layout.addWidget(self.noise_filter_button)

        self.event_identifier_button = QPushButton("Start identifying event-bytes")
        self.event_identifier_button.clicked.connect(self.event_identifier)
        layout.addWidget(self.event_identifier_button)

        # --- ADD: Bits-kontroller (nya, separata) ---
        # säkerställ att flaggor finns på MainWindow utan att behöva ändra MainWindow
        if not hasattr(self.main_window, "running_noise_filter_bits"):
            self.main_window.running_noise_filter_bits = False
        if not hasattr(self.main_window, "running_event_identifier_bits"):
            self.main_window.running_event_identifier_bits = False

        self.noise_filter_bits_button = QPushButton("Start noise filter (bits)")
        self.noise_filter_bits_button.clicked.connect(self.noise_filter_bits)
        layout.addWidget(self.noise_filter_bits_button)

        self.event_identifier_bits_button = QPushButton("Start identifying event-bits")
        self.event_identifier_bits_button.clicked.connect(self.event_identifier_bits)
        layout.addWidget(self.event_identifier_bits_button)
        # --- END ADD ---

        layout.addStretch()
        self.setLayout(layout)

    def _on_include_toggled(self, box: QCheckBox) -> None:
        other = self.include_bits if box is self.include_bytes else self.include_bytes
        if not box.isChecked() and not other.isChecked():
            box.blockSignals(True)
            box.setChecked(True)
            box.blockSignals(False)
        self.main_window.update_column_visibility()

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
            self.noise_filter_button.setText("Stop noise filter (bytes)")
        else:
            self.noise_filter_button.setText("Start noise filter (bytes)")

    def event_identifier(self) -> None:
        self.main_window.running_event_identifier = not self.main_window.running_event_identifier
        if (self.main_window.running_event_identifier):
            self.main_window.clear_event_identifier()
            self.event_identifier_button.setText("Stop identifying event-bytes")
        else:
            self.event_identifier_button.setText("Start identifying event-bytes")

    # --- ADD: Nya handlers för bits ---
    def noise_filter_bits(self) -> None:
        self.main_window.running_noise_filter_bits = not self.main_window.running_noise_filter_bits
        if self.main_window.running_noise_filter_bits:
            # ev. reset av bit-noise görs senare i MainWindow (om du vill)
            self.noise_filter_bits_button.setText("Stop noise filter (bits)")
        else:
            self.noise_filter_bits_button.setText("Start noise filter (bits)")

    def event_identifier_bits(self) -> None:
        self.main_window.running_event_identifier_bits = not self.main_window.running_event_identifier_bits
        if self.main_window.running_event_identifier_bits:
            # ev. reset av bit-event görs senare i MainWindow (om du vill)
            self.event_identifier_bits_button.setText("Stop identifying event-bits")
        else:
            self.event_identifier_bits_button.setText("Start identifying event-bits")
    # --- END ADD ---


@dataclass
class CANFrame:
    # program specific data
    row: int
    noise_filter: List[bool]
    event_identifier: List[bool]
    noise_bits: List[bool]
    event_bits: List[bool]


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
        self.running_noise_filter_bits: bool = False
        self.running_event_identifier_bits: bool = False
        self.initial_timestamp: float = 0.0

        # --- Tabell: 5 meta + 8 bytes + 8 bit‑kolumner ---
        bit_headers = [f"D{i} bits" for i in range(1, 9)]

        total_cols = 5 + 8 + 8  # 21
        self.table: QTableWidget = QTableWidget(0, total_cols)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setHorizontalHeaderLabels(
            ["Time Stamp", "ID", "Extended", "Count", "Length",
             "D1","D2","D3","D4","D5","D6","D7","D8"] + bit_headers
        )
        self.table.resizeColumnsToContents()
        self.setCentralWidget(self.table)

        # --- Installera delegate för bit‑kolumner (13..20) ---
        self.bits_delegate = BitsDelegate(self)
        for c in range(13, 21):
            self.table.setItemDelegateForColumn(c, self.bits_delegate)

        self.reader: CanReader = CanReader()
        self.reader.msg_signal.connect(self.update_table)
        self.reader.start()

        self.inspector = InspectorWidget(self)
        dock = QDockWidget("Inspector", self)
        dock.setWidget(self.inspector)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)

        self.update_column_visibility()

    def update_column_visibility(self) -> None:
        # bytes: 5..12
        show_bytes = self.inspector.include_bytes.isChecked()
        for col in range(5, 13):
            self.table.setColumnHidden(col, not show_bytes)

        # bits: 13..20
        show_bits = self.inspector.include_bits.isChecked()
        for col in range(13, 21):
            self.table.setColumnHidden(col, not show_bits)

    def update_table(self, msg: Message) -> None:
        can_id = msg.arbitration_id

        if self.initial_timestamp <= 0.0:
            self.initial_timestamp = msg.timestamp
        self.inspector.elapsed_time_label.setText(
            f"Elapsed time: {msg.timestamp - self.initial_timestamp:.1f} s"
        )

        if can_id in self.can_frames:
            frame = self.can_frames[can_id]
            row = frame.row
            count = frame.cnt + 1

            # BYTE-nivå
            if self.running_noise_filter:
                for i, old in enumerate(frame.data):
                    if i < len(msg.data) and msg.data[i] != old:
                        frame.noise_filter[i] = True

            if self.running_event_identifier:
                for i, old in enumerate(frame.data):
                    if i < len(msg.data) and msg.data[i] != old:
                        frame.event_identifier[i] = True

            # BIT-nivå XOR
            if self.running_noise_filter_bits or self.running_event_identifier_bits:
                old = frame.data
                upto = min(8, len(old), len(msg.data))
                for b in range(upto):
                    xor_val = old[b] ^ msg.data[b]
                    for k in range(8):  # bitpos (MSB→LSB)
                        abs_bit = b * 8 + (7 - k)
                        changed = bool(xor_val & (1 << (7 - k)))
                        if changed:
                            if self.running_noise_filter_bits:
                                frame.noise_bits[abs_bit] = True
                            if self.running_event_identifier_bits:
                                frame.event_bits[abs_bit] = True

            frame.time = msg.timestamp
            frame.ext = msg.is_extended_id
            frame.cnt = count
            frame.len = msg.dlc
            frame.data = msg.data

        else:
            row = self.table.rowCount()
            frame = CANFrame(
                row,
                [False] * msg.dlc,
                [False] * msg.dlc,
                [False] * 64,
                [False] * 64,
                msg.timestamp,
                msg.is_extended_id,
                1,
                msg.dlc,
                msg.data,
            )
            self.can_frames[can_id] = frame
            self.table.insertRow(row)

        # --- Meta ---
        self.table.setItem(frame.row, 0, QTableWidgetItem(f"{msg.timestamp:.0f}"))
        self.table.setItem(frame.row, 1, QTableWidgetItem(f"{can_id:03X}"))
        self.table.setItem(frame.row, 2, QTableWidgetItem(str(msg.is_extended_id)))
        self.table.setItem(frame.row, 3, QTableWidgetItem(str(frame.cnt)))
        self.table.setItem(frame.row, 4, QTableWidgetItem(str(msg.dlc)))

        # --- Bytes (5..12) ---
        for i in range(min(8, len(msg.data))):
            item = QTableWidgetItem(f"{msg.data[i]:02X}")
            if frame.noise_filter[i]:
                item.setForeground(QColor("red"))
            elif frame.event_identifier[i]:
                item.setForeground(QColor("blue"))
            self.table.setItem(frame.row, 5 + i, item)

        # --- Bitkolumner (13..20): 8 bitar i EN cell ---
        for b in range(8):
            if b < len(msg.data):
                bits = f"{msg.data[b]:08b}"
            else:
                bits = "00000000"
            # delegate färgar varje bit → vi spar bara strängen
            self.table.setItem(frame.row, 13 + b, QTableWidgetItem(bits))

    def closeEvent(self, event):
        self.reader.stop()
        self.reader.wait()
        super().closeEvent(event)

    def clear_event_identifier(self) -> None:
        # RENSAR ENBART BYTES
        for can_frame in self.can_frames.values():
            can_frame.event_identifier = [False] * can_frame.len

    def clear_event_identifier_bits(self) -> None:
        # RENSAR ENBART BITS
        for can_frame in self.can_frames.values():
            can_frame.event_bits = [False] * 64

    def clear_noise_filter(self) -> None:
        # RENSAR ENBART BYTES
        for can_frame in self.can_frames.values():
            can_frame.noise_filter = [False] * can_frame.len

    def clear_noise_filter_bits(self) -> None:
        # RENSAR ENBART BITS
        for can_frame in self.can_frames.values():
            can_frame.noise_bits = [False] * 64






if __name__ == "__main__":
    app: QApplication = QApplication(sys.argv)
    window = MainWindow()
    window.resize(960, 540)
    window.show()
    sys.exit(app.exec())