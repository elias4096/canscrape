from __future__ import annotations
from dataclasses import dataclass
import sys, csv, time
from typing import Dict, List, Optional

import can
from can import BusABC, Message

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QBrush, QCloseEvent, QColor, Qt
from PySide6.QtWidgets import (
    QApplication, QDockWidget, QLabel, QMainWindow, QPushButton,
    QRadioButton, QButtonGroup, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget, QFileDialog
)

CAN_INTERFACE = "slcan"
CAN_CHANNEL = "COM9"
CAN_BITRATE = 500000


class CsvCanReader(QThread):
    msg_signal = Signal(object)

    def __init__(self, csv_path: str):
        super().__init__()
        self.csv_path = csv_path
        self.running = True

    def run(self):
        try:
            with open(self.csv_path, newline="") as f:
                for row in csv.DictReader(f):
                    if not self.running:
                        break
                    try:
                        ts = float(row["Time Stamp"]) / 1_000_000.0
                        can_id = int(row["ID"], 16)
                    except:
                        continue
                    is_ext = row["Extended"].strip().lower() == "true"
                    dlc = int(row["LEN"])
                    data = bytearray(
                        int(row[f"D{i}"], 16) for i in range(1, 9)
                        if row[f"D{i}"].strip()
                    )
                    msg = Message(
                        timestamp=ts,
                        arbitration_id=can_id,
                        is_extended_id=is_ext,
                        dlc=dlc,
                        data=data,
                        is_rx=True
                    )
                    self.msg_signal.emit(msg)
                    time.sleep(0.001)
        except Exception as e:
            print("CSV read error:", e)

    def stop(self):
        self.running = False


class CanReader(QThread):
    msg_signal = Signal(object)

    def __init__(self):
        super().__init__()
        self.running = True

    def run(self):
        try:
            bus: BusABC = can.Bus(
                interface=CAN_INTERFACE,
                channel=CAN_CHANNEL,
                bitrate=CAN_BITRATE
            )
        except Exception as e:
            print("Failed to open CAN:", e)
            return

        while self.running:
            msg = bus.recv(0.5)
            if msg:
                self.msg_signal.emit(msg)

    def stop(self):
        self.running = False


@dataclass
class CANFrame:
    row: int
    noise1: List[bool]
    noise2: List[bool]
    time: float
    ext: bool
    cnt: int
    len: int
    data: bytearray


class InspectorWidget(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window

        layout = QVBoxLayout()
        self.elapsed_label = QLabel("Elapsed time: 0.0 s")
        layout.addWidget(self.elapsed_label)

        self.live_radio = QRadioButton("Live CAN (slcan/COM)")
        self.csv_radio = QRadioButton("CSV Replay")
        self.live_radio.setChecked(True)

        self.group = QButtonGroup()
        self.group.addButton(self.live_radio)
        self.group.addButton(self.csv_radio)

        layout.addWidget(self.live_radio)
        layout.addWidget(self.csv_radio)

        self.csv_button = QPushButton("Open CSV File...")
        self.csv_button.clicked.connect(self.select_csv_file)
        layout.addWidget(self.csv_button)

        self.start_button = QPushButton("Start")
        self.start_button.clicked.connect(
            lambda: main_window.start_reader(self.csv_radio.isChecked())
        )
        layout.addWidget(self.start_button)

        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(main_window.stop_reader)
        layout.addWidget(self.stop_button)

        self.clear_button = QPushButton("Clear table")
        self.clear_button.clicked.connect(main_window.clear_all)
        layout.addWidget(self.clear_button)

        self.noise1_button = QPushButton("Start noise calc")
        self.noise1_button.clicked.connect(self.toggle_noise1)
        layout.addWidget(self.noise1_button)

        self.noise2_button = QPushButton("Start identify calc")
        self.noise2_button.clicked.connect(self.toggle_noise2)
        layout.addWidget(self.noise2_button)

        layout.addStretch()
        self.setLayout(layout)

    def select_csv_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open CSV", "", "CSV Files (*.csv)")
        if path:
            self.main_window.csv_path = path

    def toggle_noise1(self):
        m = self.main_window
        m.running_noise1 = not m.running_noise1
        self.noise1_button.setText(
            "Stop noise calc" if m.running_noise1 else "Start noise calc"
        )

    def toggle_noise2(self):
        m = self.main_window
        m.running_noise2 = not m.running_noise2
        self.noise2_button.setText(
            "Stop identify calc" if m.running_noise2 else "Start identify calc"
        )


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CAN Scrape")

        self.can_frames: Dict[int, CANFrame] = {}
        self.running_noise1 = False
        self.running_noise2 = False
        self.initial_timestamp = 0.0
        self.csv_path = ""
        self.reader = None

        self.table = QTableWidget(0, 14)
        self.table.setHorizontalHeaderLabels([
            "Time Stamp", "ID", "Extended", "Count", "Length",
            "D1","D2","D3","D4","D5","D6","D7","D8","Bits (64)"
        ])
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.setCentralWidget(self.table)

        dock = QDockWidget("Inspector", self)
        self.inspector = InspectorWidget(self)
        dock.setWidget(self.inspector)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)

    def start_reader(self, use_csv: bool):
        self.stop_reader()
        self.reader = CsvCanReader(self.csv_path) if use_csv else CanReader()
        self.reader.msg_signal.connect(self.update_table)
        self.reader.start()

    def stop_reader(self):
        if self.reader:
            self.reader.stop()
            self.reader.wait()
            self.reader = None

    def update_table(self, msg: Message):
        can_id = msg.arbitration_id

        if not self.initial_timestamp:
            self.initial_timestamp = msg.timestamp

        elapsed = msg.timestamp - self.initial_timestamp
        self.inspector.elapsed_label.setText(f"Elapsed time: {elapsed:.1f} s")

        if can_id not in self.can_frames:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.can_frames[can_id] = CANFrame(
                row=row,
                noise1=[False] * msg.dlc,
                noise2=[False] * msg.dlc,
                time=msg.timestamp,
                ext=msg.is_extended_id,
                cnt=1,
                len=msg.dlc,
                data=msg.data
            )
        frame = self.can_frames[can_id]
        frame.cnt += 1

        lim = min(len(msg.data), frame.len)
        if self.running_noise1:
            for i in range(lim):
                if msg.data[i] != frame.data[i]:
                    frame.noise1[i] = True

        if self.running_noise2:
            for i in range(lim):
                if msg.data[i] != frame.data[i]:
                    frame.noise2[i] = True

        frame.time = msg.timestamp
        frame.ext = msg.is_extended_id
        frame.len = msg.dlc
        frame.data = msg.data

        row = frame.row
        self.table.setItem(row, 0, QTableWidgetItem(f"{msg.timestamp:.0f}"))
        self.table.setItem(row, 1, QTableWidgetItem(f"{can_id:03X}"))
        self.table.setItem(row, 2, QTableWidgetItem(str(frame.ext)))
        self.table.setItem(row, 3, QTableWidgetItem(str(frame.cnt)))
        self.table.setItem(row, 4, QTableWidgetItem(str(msg.dlc)))

        for i in range(msg.dlc):
            item = QTableWidgetItem(f"{msg.data[i]:02X}")
            if frame.noise1[i]:
                item.setForeground(QBrush(QColor("red")))
            elif frame.noise2[i]:
                item.setForeground(QBrush(QColor("blue")))
            self.table.setItem(row, 5 + i, item)

        bits = " ".join(f"{b:08b}" for b in msg.data[:8])
        self.table.setItem(row, 13, QTableWidgetItem(bits))

    def clear_all(self):
        self.running_noise1 = False
        self.running_noise2 = False
        self.initial_timestamp = 0.0
        self.can_frames.clear()
        self.table.setRowCount(0)

    def closeEvent(self, e: QCloseEvent):
        self.stop_reader()
        super().closeEvent(e)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainWindow()
    w.resize(1100, 600)
    w.show()
    sys.exit(app.exec())
