import re
import threading
import can

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QLabel, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget
)


# --------------------------------------------------------------------------- #
#  CAN listener worker thread
# --------------------------------------------------------------------------- #
class CANListenerThread(QThread):
    bit_update = Signal(str, int, int)
    # arguments: CAN-ID (hex string), bit number, value(0/1)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.running = True

        # python-can interface
        self.bus = can.ThreadSafeBus(
            interface="slcan",
            channel="COM9",
            bitrate=500000
        )

    def run(self):
        while self.running:
            msg = self.bus.recv(0.1)
            if msg is None:
                continue

            can_id = f"{msg.arbitration_id:04X}"

            # ✅ Extract reversed bits using 1-based bit numbering
            for byte_index, byte_val in enumerate(msg.data):

                for bit_zero_based in range(8):

                    # Convert to 1‑based (1–8)
                    bit_1based = bit_zero_based + 1

                    # Apply the 1‑based reversal formula
                    reversed_1based = 8 - bit_1based + 1

                    # Convert back to zero-based
                    reversed_zero_based = reversed_1based - 1

                    # Extract the reversed bit value
                    bit_val = (byte_val >> reversed_zero_based) & 1

                    # Compute the global reversed bit number (1-based)
                    bit_num = byte_index * 8 + reversed_1based

                    # Emit
                    self.bit_update.emit(can_id, bit_num, bit_val)

    def stop(self):
        self.running = False
        self.wait(500)


# --------------------------------------------------------------------------- #
#  Main widget
# --------------------------------------------------------------------------- #
class AnalysisResultWidget(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        self.status_label = QLabel("No analysis run yet.")
        self.status_label.setStyleSheet("color: #888; font-style: italic;")
        layout.addWidget(self.status_label)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Event / ID", "Bits (changes)", "Live"])
        self.tree.setColumnWidth(0, 260)
        self.tree.setColumnWidth(2, 80)
        self.tree.setAlternatingRowColors(True)
        self.tree.setEditTriggers(QTreeWidget.EditTrigger.NoEditTriggers)
        self.tree.setFont(QFont("Consolas", 9))
        layout.addWidget(self.tree)

        # Mapping: (id, bit) → QTreeWidgetItem
        self.bit_items = {}

        # Start background CAN thread
        self.can_thread = CANListenerThread()
        self.can_thread.bit_update.connect(self.update_live_bit)
        self.can_thread.start()

    # ------------------------------------------------------------------ #

    def update_live_bit(self, can_id: str, bit_num: int, value: int):
        key = (can_id, bit_num)
        if key not in self.bit_items:
            return

        item = self.bit_items[key]
        item.setText(2, str(value))
        item.setForeground(2, Qt.GlobalColor.green if value else Qt.GlobalColor.red)

    # ------------------------------------------------------------------ #

    def show_running(self):
        self.status_label.setText("Analysis running…")
        self.status_label.setStyleSheet("color: #e0a040; font-style: italic;")
        self.tree.clear()
        self.bit_items.clear()

    def show_error(self, message: str):
        self.status_label.setText(f"Error: {message}")
        self.status_label.setStyleSheet("color: #e06060; font-style: italic;")

    def load_output(self, raw_output: str):
        self.tree.clear()
        self.bit_items.clear()

        current_event_item: QTreeWidgetItem | None = None

        for line in raw_output.splitlines():
            stripped = line.strip()
            if not stripped or stripped == "Exklusiva bitar per event:":
                continue

            # Event header
            if stripped.endswith(":") and not re.match(r'^[0-9A-Fa-f]{4}:', stripped):
                event_name = stripped[:-1]
                current_event_item = QTreeWidgetItem(self.tree, [event_name, "", ""])
                current_event_item.setFont(0, QFont("Segoe UI", 9, QFont.Weight.Bold))
                current_event_item.setExpanded(True)
                continue

            if stripped == "Inga exklusiva bitar":
                if current_event_item:
                    child = QTreeWidgetItem(current_event_item, ["—", "no exclusive bits", ""])
                    child.setForeground(0, Qt.GlobalColor.gray)
                    child.setForeground(1, Qt.GlobalColor.gray)
                continue

            # CAN-ID entry
            id_match = re.match(r'^([0-9A-Fa-f]{4}):\s*(.+)$', stripped)
            if id_match and current_event_item:
                can_id = id_match.group(1)
                bits_str = id_match.group(2)

                id_item = QTreeWidgetItem(current_event_item, [can_id, "", ""])
                id_item.setExpanded(True)

                # Parse bNN(N)
                for bit_match in re.finditer(r'b(\d+)\((\d+)\)', bits_str):

                    original_bit_1based = int(bit_match.group(1))
                    changes = bit_match.group(2)

                    # Convert to 1-based per-byte indexing
                    byte_index = (original_bit_1based - 1) // 8
                    bit_in_byte_1based = ((original_bit_1based - 1) % 8) + 1

                    # Reverse using the same rule as live CAN data
                    reversed_1based = 8 - bit_in_byte_1based + 1

                    # Global reversed bit
                    bit_num = byte_index * 8 + reversed_1based

                    bit_item = QTreeWidgetItem(id_item, [
                        f"  bit {bit_num}",
                        f"{changes} change(s)",
                        "?"
                    ])

                    self.bit_items[(can_id, bit_num)] = bit_item

        if self.tree.topLevelItemCount() == 0:
            self.status_label.setText("Analysis complete — no results.")
            self.status_label.setStyleSheet("color: #888; font-style: italic;")
        else:
            self.status_label.setText("Analysis complete.")
            self.status_label.setStyleSheet("color: #6cc96c; font-style: italic;")

    # ------------------------------------------------------------------ #

    def closeEvent(self, event):
        self.can_thread.stop()
        super().closeEvent(event)