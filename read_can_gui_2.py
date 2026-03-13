from __future__ import annotations

import sys
from typing import Dict, Optional, Tuple
import xml.etree.ElementTree as ET

import can
from can import BusABC, Message

from PySide6.QtCore import QThread, Signal, Qt, QTimer
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QDockWidget,
    QWidget,
    QVBoxLayout,
    QLabel,
    QScrollArea,
    QTextEdit,
)


CAN_INTERFACE = "pcan"
CAN_CHANNEL = "PCAN_USBBUS1"
CAN_BITRATE = 500_000


class CanReader(QThread):
    msg_signal: Signal = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.running: bool = True

    def run(self) -> None:
        try:
            bus: BusABC = can.Bus(
                interface=CAN_INTERFACE,
                channel=CAN_CHANNEL,
                bitrate=CAN_BITRATE,
            )
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

        self.latest_timestamp_us: int = 0

        # =====================================================================
        # CAN TABLE
        # =====================================================================
        self.table: QTableWidget = QTableWidget(0, 13)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setHorizontalHeaderLabels(
            [
                "Time (µs)", "ID", "Extended", "Count", "Length",
                "D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8",
            ]
        )
        self.setCentralWidget(self.table)
        self.rows_by_id: Dict[int, Tuple[int, int]] = {}

        # CAN reader thread
        self.reader: CanReader = CanReader()
        self.reader.msg_signal.connect(self.update_table)
        self.reader.start()

        # =====================================================================
        # INSPECTOR DOCK
        # =====================================================================
        inspector_dock = QDockWidget("Inspector", self)
        inspector_dock.setAllowedAreas(Qt.RightDockWidgetArea)

        inspector_widget = QWidget()
        inspector_layout = QVBoxLayout(inspector_widget)

        # Timestamp tools
        self.timestamp_button = QPushButton("Show Latest Timestamp")
        self.timestamp_button.clicked.connect(self.show_latest_timestamp)

        self.timestamp_label = QLabel("Timestamp: - µs")

        inspector_layout.addWidget(self.timestamp_button)
        inspector_layout.addWidget(self.timestamp_label)

        # =====================================================================
        # SNAPSHOT TOOLS
        # =====================================================================
        self.snapshot1 = {}
        self.snapshot2 = {}

        btn_snap1 = QPushButton("Set Snapshot 1")
        btn_snap1.clicked.connect(self.set_snapshot_1)

        btn_snap2 = QPushButton("Set Snapshot 2")
        btn_snap2.clicked.connect(self.set_snapshot_2)

        btn_compare = QPushButton("Compare Snapshots")
        btn_compare.clicked.connect(self.compare_snapshots)

        inspector_layout.addWidget(btn_snap1)
        inspector_layout.addWidget(btn_snap2)
        inspector_layout.addWidget(btn_compare)

        # =====================================================================
        # NOISE CALCULATION
        # =====================================================================
        self.noise_active = False
        self.noise_first_values = {}
        self.noise_ids = set()

        btn_noise = QPushButton("Calculate Noise")
        btn_noise.clicked.connect(self.start_noise_capture)

        self.noise_status_label = QLabel("Noise capture: idle")
        self.noise_list_label = QLabel("Noise IDs: none")

        inspector_layout.addWidget(btn_noise)
        inspector_layout.addWidget(self.noise_status_label)
        inspector_layout.addWidget(self.noise_list_label)

        # =====================================================================
        # SNAPSHOT COMPARISON OUTPUT
        # =====================================================================
        inspector_layout.addWidget(QLabel("Comparison Result:"))

        self.snapshot_output = QTextEdit()
        self.snapshot_output.setReadOnly(True)
        self.snapshot_output.setMinimumHeight(250)
        inspector_layout.addWidget(self.snapshot_output)

        inspector_dock.setWidget(inspector_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, inspector_dock)

        # =====================================================================
        # ACTION BUTTONS (XML)
        # =====================================================================
        self.load_actions_from_xml("actions.xml")

    # =============================================================================
    # XML ACTIONS
    # =============================================================================
    def load_actions_from_xml(self, filename: str):
        self.actions = {}

        try:
            tree = ET.parse(filename)
            root = tree.getroot()
        except Exception as e:
            print("Failed to load XML:", e)
            return

        dock = QDockWidget("Actions", self)
        dock.setAllowedAreas(Qt.RightDockWidgetArea)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        container = QWidget()
        layout = QVBoxLayout(container)

        for action_el in root.findall("Action"):
            name = action_el.get("name", "Unknown")
            i1 = action_el.findtext("Instruction1", "")
            delay = int(action_el.findtext("Delay", "1"))
            i2 = action_el.findtext("Instruction2", "")

            self.actions[name] = (i1, delay, i2)

            btn = QPushButton(name)
            btn.clicked.connect(lambda _, n=name: self.handle_action_click(n))
            layout.addWidget(btn)

        layout.addStretch()
        scroll.setWidget(container)
        dock.setWidget(scroll)

        self.addDockWidget(Qt.RightDockWidgetArea, dock)

    # =============================================================================
    # ACTION EXECUTION
    # =============================================================================
    def handle_action_click(self, action_name: str):
        instr1, delay, instr2 = self.actions[action_name]
        self.timestamp_label.setText(f"{action_name}: {instr1}")

        QTimer.singleShot(
            delay * 1000,
            lambda: self.timestamp_label.setText(f"{action_name}: {instr2}")
        )

    # =============================================================================
    # SNAPSHOT FUNCTIONS
    # =============================================================================
    def create_snapshot(self) -> Dict[int, dict]:
        snapshot = {}
        for can_id, (row, _) in self.rows_by_id.items():
            ts = int(self.table.item(row, 0).text())
            dlc = int(self.table.item(row, 4).text())
            data = []
            for i in range(8):
                cell = self.table.item(row, 5 + i)
                if cell:
                    data.append(int(cell.text(), 16))
            snapshot[can_id] = {"timestamp": ts, "dlc": dlc, "data": data}
        return snapshot

    def set_snapshot_1(self):
        self.snapshot1 = self.create_snapshot()
        self.snapshot_output.setPlainText("Snapshot 1 stored.")

    def set_snapshot_2(self):
        self.snapshot2 = self.create_snapshot()
        self.snapshot_output.setPlainText("Snapshot 2 stored.")

    # =============================================================================
    # SNAPSHOT COMPARISON
    # =============================================================================
    def compare_snapshots(self):
        s1 = self.snapshot1
        s2 = self.snapshot2

        output = []

        all_ids = sorted(set(s1.keys()) | set(s2.keys()))

        for cid in all_ids:
            if cid in self.noise_ids:
                continue  # skip noise completely

            cid_hex = f"{cid:03X}"

            if cid not in s1:
                output.append(f"[ADDED] ID {cid_hex}\n")
                continue

            if cid not in s2:
                output.append(f"[REMOVED] ID {cid_hex}\n")
                continue

            old = s1[cid]
            new = s2[cid]

            if old["dlc"] != new["dlc"] or old["data"] != new["data"]:
                old_str = " ".join(f"{b:02X}" for b in old["data"])
                new_str = " ".join(f"{b:02X}" for b in new["data"])
                output.append(
                    f"[CHANGED] ID {cid_hex}\n"
                    f"  Old: {old_str}\n"
                    f"  New: {new_str}\n"
                )

        if not output:
            self.snapshot_output.setPlainText("No differences found.")
        else:
            self.snapshot_output.setPlainText("\n".join(output))

    # =============================================================================
    # NOISE CAPTURE
    # =============================================================================
    def start_noise_capture(self):
        if self.noise_active:
            return

        self.noise_active = True
        self.noise_first_values = {}
        self.noise_ids = set()

        self.noise_status_label.setText("Calculating noise... 10s remaining")
        self.noise_list_label.setText("Noise IDs: (calculating)")

        self.noise_seconds_left = 10

        def tick():
            if self.noise_seconds_left == 0:
                self.noise_active = False
                self.noise_status_label.setText("Noise capture: complete")

                if not self.noise_ids:
                    self.noise_list_label.setText("Noise IDs: none")
                else:
                    ids = ", ".join(f"0x{x:03X}" for x in sorted(self.noise_ids))
                    self.noise_list_label.setText(f"Noise IDs: {ids}")
                return

            self.noise_status_label.setText(
                f"Calculating noise... {self.noise_seconds_left}s remaining"
            )
            self.noise_seconds_left -= 1
            QTimer.singleShot(1000, tick)

        tick()

    # =============================================================================
    # CAN TABLE UPDATE
    # =============================================================================
    def update_table(self, msg: Message) -> None:
        ts_us = int(msg.timestamp * 1_000_000)
        self.latest_timestamp_us = ts_us

        cid = msg.arbitration_id

        if cid in self.rows_by_id:
            row, count = self.rows_by_id[cid]
            count += 1
        else:
            row = self.table.rowCount()
            self.table.insertRow(row)
            count = 1

        self.rows_by_id[cid] = (row, count)

        self.table.setItem(row, 0, QTableWidgetItem(str(ts_us)))
        self.table.setItem(row, 1, QTableWidgetItem(f"{cid:03X}"))
        self.table.setItem(row, 2, QTableWidgetItem(str(msg.is_extended_id)))
        self.table.setItem(row, 3, QTableWidgetItem(str(count)))
        self.table.setItem(row, 4, QTableWidgetItem(str(msg.dlc)))

        payload = []
        for i in range(8):
            if i < len(msg.data):
                v = msg.data[i]
                payload.append(v)
        for i in range(len(payload)):
            self.table.setItem(row, 5 + i, QTableWidgetItem(f"{payload[i]:02X}"))

        # --------------------------------------------------------
        # NOISE DETECTION
        # --------------------------------------------------------
        if self.noise_active:
            if cid not in self.noise_first_values:
                self.noise_first_values[cid] = payload.copy()
            else:
                if self.noise_first_values[cid] != payload:
                    self.noise_ids.add(cid)

    # =============================================================================
    # DISPLAY TIMESTAMP
    # =============================================================================
    def show_latest_timestamp(self):
        self.timestamp_label.setText(f"Timestamp: {self.latest_timestamp_us} µs")

    # =============================================================================
    # CLEAN SHUTDOWN
    # =============================================================================
    def closeEvent(self, event: QCloseEvent) -> None:
        self.reader.stop()
        self.reader.wait()
        super().closeEvent(event)


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainWindow()
    w.resize(1300, 750)
    w.show()
    sys.exit(app.exec())
