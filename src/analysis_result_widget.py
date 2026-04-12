import re
import threading
import can

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QLabel, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget
)

from autoencoder_detector2 import run_full_ml_pipeline


# --------------------------------------------------------------------------- #
# ML Worker (NEW, SAFE)
# --------------------------------------------------------------------------- #
class MLWorker(QThread):
    result_ready = Signal(dict)
    error = Signal(str)

    def __init__(self, baseline, events, actions, exclusive):
        super().__init__()
        self.baseline = baseline
        self.events = events
        self.actions = actions
        self.exclusive = exclusive

    def run(self):
        try:
            result = run_full_ml_pipeline(
                self.baseline,
                self.events,
                self.actions,
                self.exclusive
            )
            self.result_ready.emit(result)
        except Exception as e:
            self.error.emit(str(e))



# --------------------------------------------------------------------------- #
#  CAN listener worker thread (UNCHANGED)
# --------------------------------------------------------------------------- #
class CANListenerThread(QThread):
    bit_update = Signal(str, int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.running = True

        try:
            self.bus = can.ThreadSafeBus(
                interface="slcan",
                channel="COM9",
                bitrate=500000
            )
        except Exception as e:
            print(f"CAN ERROR: {e}")
            self.bus = None

    def run(self):
        if self.bus is None:
            while self.running:
                self.msleep(100)
            return

        while self.running:
            msg = self.bus.recv(0.1)
            if msg is None:
                continue

            can_id = f"{msg.arbitration_id:04X}"

            for byte_index, byte_val in enumerate(msg.data):
                for bit_zero_based in range(8):

                    bit_1based = bit_zero_based + 1
                    reversed_1based = 8 - bit_1based + 1
                    reversed_zero_based = reversed_1based - 1

                    bit_val = (byte_val >> reversed_zero_based) & 1
                    bit_num = byte_index * 8 + reversed_1based

                    self.bit_update.emit(can_id, bit_num, bit_val)

    def stop(self):
        self.running = False
        self.wait(500)



# --------------------------------------------------------------------------- #
#  Main widget
# --------------------------------------------------------------------------- #
class AnalysisResultWidget(QWidget):
    def __init__(self, settings):
        super().__init__()

        self.settings = settings

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        self.status_label = QLabel("No analysis run yet.")
        self.status_label.setStyleSheet("color: #888; font-style: italic;")
        layout.addWidget(self.status_label)

        self.tree = QTreeWidget()

        # ✅ NEW COLUMN ADDED (safe)
        self.tree.setHeaderLabels(["Event / ID", "Bits (changes)", "Live", "Deviation"])

        self.tree.setColumnWidth(0, 260)
        self.tree.setColumnWidth(1, 140)
        self.tree.setColumnWidth(2, 80)
        self.tree.setColumnWidth(3, 120)

        self.tree.setAlternatingRowColors(True)
        self.tree.setEditTriggers(QTreeWidget.EditTrigger.NoEditTriggers)
        self.tree.setFont(QFont("Consolas", 9))
        layout.addWidget(self.tree)

        self.bit_items = {}
        self.id_items = {}

        self.can_thread = CANListenerThread()
        self.can_thread.bit_update.connect(self.update_live_bit)
        self.can_thread.start()

    def show_running(self):
        self.status_label.setText("Analysis running…")
        self.status_label.setStyleSheet("color: #e0a040; font-style: italic;")
        self.tree.clear()
        self.bit_items.clear()
        self.id_items.clear()

    # ------------------------------------------------------------------ #

    def update_live_bit(self, can_id: str, bit_num: int, value: int):
        key = (can_id, bit_num)
        if key not in self.bit_items:
            return

        item = self.bit_items[key]
        item.setText(2, str(value))

        item.setForeground(2, Qt.GlobalColor.green if value else Qt.GlobalColor.red)

    # ------------------------------------------------------------------ #

    def apply_deviation_results(self, deviation_dict: dict):
        """
        Injects ML results into the rightmost column.
        """
        for event_name, per_id in deviation_dict.items():

            # ✅ Qt 6 safe match flag
            items = self.tree.findItems(
                event_name, Qt.MatchFlag.MatchExactly, 0
            )
            if not items:
                continue

            event_item = items[0]

            for hex_id, score in per_id.items():
                cid = hex_id.replace("0x", "").upper().zfill(4)

                # locate ID row
                for i in range(event_item.childCount()):
                    child = event_item.child(i)
                    if child.text(0) == cid:
                        child.setText(3, f"{score:.3f}")
                        break

        self.status_label.setText("Analysis complete.")
        self.status_label.setStyleSheet("color: #6cc96c; font-style: italic;")

    # ------------------------------------------------------------------ #

    def load_output(self, raw_output: str):
        """
        Builds tree and starts ML automatically.
        """
        self.tree.clear()
        self.bit_items.clear()
        self.id_items.clear()

        current_event_item = None

        for line in raw_output.splitlines():
            stripped = line.strip()
            if not stripped or stripped == "Exklusiva bitar per event:":
                continue

            # Event header
            if (
                stripped.endswith(":")
                and not re.match(r'^[0-9A-Fa-f]{4}:', stripped)
            ):
                event_name = stripped[:-1]
                current_event_item = QTreeWidgetItem(
                    self.tree, [event_name, "", "", ""]
                )
                current_event_item.setFont(0, QFont("Segoe UI", 9, QFont.Weight.Bold))
                current_event_item.setExpanded(True)
                continue

            # CAN ID row
            id_match = re.match(r'^([0-9A-Fa-f]{4}):\s*(.+)$', stripped)
            if id_match and current_event_item:

                cid = id_match.group(1)
                bits_str = id_match.group(2)

                id_item = QTreeWidgetItem(current_event_item, [cid, "", "", ""])
                self.id_items[cid] = id_item
                id_item.setExpanded(True)

                # Parse bits
                for bit_match in re.finditer(r'b(\d+)\((\d+)\)', bits_str):

                    original_bit = int(bit_match.group(1))
                    changes = bit_match.group(2)

                    byte_index = (original_bit - 1) // 8
                    bit_in_byte = ((original_bit - 1) % 8) + 1
                    reversed_1based = 8 - bit_in_byte + 1
                    bit_num = byte_index * 8 + reversed_1based

                    bit_item = QTreeWidgetItem(id_item, [
                        f"  bit {bit_num}",
                        f"{changes} change(s)",
                        "?",
                        ""
                    ])

                    self.bit_items[(cid, bit_num)] = bit_item

        # ✅ START ML AFTER TREE IS BUILT
        self.status_label.setText("Running anomaly detection…")

        #print(self.settings.baseline_path)
        #print(self.settings.last_export_raw)
        #print(self.settings.last_export_json)

        self.worker = MLWorker(
            self.settings.baseline_path,
            self.settings.last_export_raw,
            self.settings.last_export_json,
            raw_output
        )
        self.worker.result_ready.connect(self.apply_deviation_results)
        self.worker.error.connect(self.show_error)
        self.worker.start()

    # ------------------------------------------------------------------ #

    def show_error(self, message: str):
        self.status_label.setText(f"Error: {message}")
        self.status_label.setStyleSheet("color: red; font-style: italic;")

    def closeEvent(self, event):
        self.can_thread.stop()
        super().closeEvent(event)