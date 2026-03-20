from __future__ import annotations

import sys
from typing import Dict, Optional, Tuple, List
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

        # Latest timestamp (µs) from most recent CAN frame
        self.latest_timestamp_us: int = 0

        # Full frame history (grows indefinitely by design - H1)
        # Each entry: {"timestamp": int_us, "can_id": int, "dlc": int, "data": List[int]}
        self.frame_history: List[dict] = []

        # =====================================================================
        # CAN TABLE (latest values per CAN ID)
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
        # Map CAN ID -> (row index, count)
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
        # SNAPSHOT TOOLS (F2: timestamps only)
        # =====================================================================
        self.snapshot1_time_us: Optional[int] = None
        self.snapshot2_time_us: Optional[int] = None

        btn_snap1 = QPushButton("Set Snapshot 1 (T1)")
        btn_snap1.clicked.connect(self.set_snapshot_1)

        btn_snap2 = QPushButton("Set Snapshot 2 (T2)")
        btn_snap2.clicked.connect(self.set_snapshot_2)

        btn_compare = QPushButton("Compare Snapshots (T1–T2)")
        btn_compare.clicked.connect(self.compare_snapshots)

        inspector_layout.addWidget(btn_snap1)
        inspector_layout.addWidget(btn_snap2)
        inspector_layout.addWidget(btn_compare)

        # =====================================================================
        # NOISE CALCULATION
        # =====================================================================
        self.noise_active: bool = False
        # can_id -> (dlc, first_data_list)
        self.noise_first_values: Dict[int, Tuple[int, List[int]]] = {}
        # IDs detected as noise (any change in 10s window)
        self.noise_ids: set[int] = set()

        btn_noise = QPushButton("Calculate Noise (10s)")
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
        self.snapshot_output.setMinimumHeight(280)
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
    # SNAPSHOT FUNCTIONS (F2: timestamps only)
    # =============================================================================
    def set_snapshot_1(self):
        if self.latest_timestamp_us == 0:
            self.snapshot_output.setPlainText(
                "Snapshot 1 not set: no CAN frames received yet."
            )
            return
        self.snapshot1_time_us = self.latest_timestamp_us
        self.snapshot_output.setPlainText(
            f"Snapshot 1 (T1) set at {self.snapshot1_time_us} µs "
            f"({self.snapshot1_time_us / 1000.0:.3f} ms)"
        )

    def set_snapshot_2(self):
        if self.latest_timestamp_us == 0:
            self.snapshot_output.setPlainText(
                "Snapshot 2 not set: no CAN frames received yet."
            )
            return
        self.snapshot2_time_us = self.latest_timestamp_us
        self.snapshot_output.setPlainText(
            f"Snapshot 2 (T2) set at {self.snapshot2_time_us} µs "
            f"({self.snapshot2_time_us / 1000.0:.3f} ms)"
        )

    # =============================================================================
    # SNAPSHOT COMPARISON (T1–T2, grouped by CAN ID, only changes, show µs and ms)
    # =============================================================================
    def compare_snapshots(self):
        T1 = self.snapshot1_time_us
        T2 = self.snapshot2_time_us

        if T1 is None or T2 is None:
            self.snapshot_output.setPlainText(
                "Please set both Snapshot 1 and Snapshot 2 before comparing."
            )
            return
        if T2 < T1:
            self.snapshot_output.setPlainText(
                "Snapshot 2 (T2) must be >= Snapshot 1 (T1). Please set again."
            )
            return

        # Extract frames in the interval [T1, T2]
        window_frames = [f for f in self.frame_history if T1 <= f["timestamp"] <= T2]

        if not window_frames:
            self.snapshot_output.setPlainText(
                "No frames found in the selected interval."
            )
            return

        # Group frames by CAN ID, exclude noise IDs
        frames_by_id: Dict[int, List[dict]] = {}
        for f in window_frames:
            cid = f["can_id"]
            if cid in self.noise_ids:
                continue
            frames_by_id.setdefault(cid, []).append(f)

        if not frames_by_id:
            self.snapshot_output.setPlainText(
                "No frames to display in the interval (all excluded by noise filtering)."
            )
            return

        # Build output: Grouped by CAN ID, show only changes (A2)
        lines: List[str] = []
        header = (
            f"Changes between {T1} µs ({T1 / 1000.0:.3f} ms) and "
            f"{T2} µs ({T2 / 1000.0:.3f} ms):"
        )
        lines.append(header)
        lines.append("")  # blank line

        for cid in sorted(frames_by_id.keys()):
            group = frames_by_id[cid]
            # Sort by timestamp within the group
            group.sort(key=lambda x: x["timestamp"])

            # Reduce to only changes (A2): keep first, then only when (dlc, data) differs from last kept
            reduced: List[dict] = []
            last_sig = None  # (dlc, tuple(data))
            for fr in group:
                sig = (fr["dlc"], tuple(fr["data"]))
                if last_sig is None or sig != last_sig:
                    reduced.append(fr)
                    last_sig = sig

            if not reduced:
                continue

            lines.append(f"ID {cid:03X}:")
            for fr in reduced:
                ts_us = fr["timestamp"]
                ts_ms = ts_us / 1000.0
                data_str = " ".join(f"{b:02X}" for b in fr["data"])
                lines.append(f"  {ts_us} µs ({ts_ms:.3f} ms)  →  {data_str}")
            lines.append("")  # blank line between IDs

        if len(lines) <= 2:
            self.snapshot_output.setPlainText("No changes found in the interval.")
        else:
            self.snapshot_output.setPlainText("\n".join(lines))

    # =============================================================================
    # NOISE CAPTURE (10s, live countdown). Any change (dlc or data) marks an ID as noise.
    # =============================================================================
    def start_noise_capture(self):
        if self.noise_active:
            return

        self.noise_active = True
        self.noise_first_values.clear()
        self.noise_ids.clear()

        self.noise_seconds_left = 10
        self.noise_status_label.setText("Calculating noise... 10s remaining")
        self.noise_list_label.setText("Noise IDs: (calculating)")

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
    # CAN TABLE UPDATE + FRAME HISTORY APPEND + NOISE DETECTION
    # =============================================================================
    def update_table(self, msg: Message) -> None:
        # Convert timestamp seconds -> microseconds
        ts_us = int(msg.timestamp * 1_000_000)
        self.latest_timestamp_us = ts_us

        cid = msg.arbitration_id

        # Update / Insert row in the table
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

        # Prepare payload (list of ints). We keep exactly msg.dlc bytes (up to 8).
        payload: List[int] = [int(b) for b in bytes(msg.data[: min(msg.dlc, 8)])]
        for i, val in enumerate(payload):
            self.table.setItem(row, 5 + i, QTableWidgetItem(f"{val:02X}"))
        # (Optional) You could clear remaining cells if DLC < 8.

        # Append to frame history (H1: grows indefinitely)
        self.frame_history.append({
            "timestamp": ts_us,
            "can_id": cid,
            "dlc": int(msg.dlc),
            "data": payload.copy(),
        })

        # Noise detection (active window): mark IDs whose (dlc, data) change at least once
        if self.noise_active:
            sig = (int(msg.dlc), tuple(payload))
            if cid not in self.noise_first_values:
                self.noise_first_values[cid] = (sig[0], list(sig[1]))
            else:
                first_dlc, first_data = self.noise_first_values[cid]
                if first_dlc != sig[0] or first_data != list(sig[1]):
                    self.noise_ids.add(cid)

    # =============================================================================
    # DISPLAY LATEST TIMESTAMP
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