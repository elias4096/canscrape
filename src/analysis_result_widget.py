import re
import json
import can

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    QPushButton,
    QFileDialog,
)

from autoencoder_detector2 import run_full_ml_pipeline
from settings import InputMode


# --------------------------------------------------------------------------- #
# ML Worker
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
                self.exclusive,
            )
            self.result_ready.emit(result)
        except Exception as e:
            self.error.emit(str(e))


# --------------------------------------------------------------------------- #
# Main widget
# --------------------------------------------------------------------------- #
class AnalysisResultWidget(QWidget):
    def __init__(self, settings):
        super().__init__()

        self.settings = settings

        settings.setInputMode(InputMode.SerialPort)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        self.status_label = QLabel("No analysis run yet.")
        self.status_label.setStyleSheet("color: #888; font-style: italic;")
        layout.addWidget(self.status_label)

        self.export_btn = QPushButton("Export selected bits (JSON)")
        self.export_btn.clicked.connect(self.export_selected_bits)
        layout.addWidget(self.export_btn)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(
            ["Event / ID", "Bits (changes)", "Live", "Deviation", "Select"]
        )
        self.tree.setColumnWidth(0, 260)
        self.tree.setColumnWidth(1, 140)
        self.tree.setColumnWidth(2, 80)
        self.tree.setColumnWidth(3, 120)
        self.tree.setColumnWidth(4, 70)

        self.tree.setAlternatingRowColors(True)
        self.tree.setEditTriggers(QTreeWidget.EditTrigger.NoEditTriggers)
        self.tree.setFont(QFont("Consolas", 9))
        layout.addWidget(self.tree)

        self.bit_items = {}
        self.selectable_bits = {}

        # ------------------------------------------------------------------ #
        # ✅ Use settings.reader instead of custom CAN thread
        # ------------------------------------------------------------------ #
        self.reader = self.settings.reader
        if self.reader is not None:
            self.reader.msg_signal.connect(self.on_can_message)

            # Ensure reader is actually running
            if not self.reader.isRunning():
                self.reader.start()

    # ------------------------------------------------------------------ #
    # CAN message handling (bit decoding)
    # ------------------------------------------------------------------ #
    def on_can_message(self, msg: can.Message):
        can_id = f"{msg.arbitration_id:04X}"

        for byte_index, byte_val in enumerate(msg.data):
            for bit_zero_based in range(8):
                bit_1based = bit_zero_based + 1
                reversed_1based = 8 - bit_1based + 1
                reversed_zero_based = reversed_1based - 1

                # ✅ Correct Python bit extraction
                bit_val = (byte_val >> reversed_zero_based) & 1
                bit_num = byte_index * 8 + reversed_1based

                self.update_live_bit(can_id, bit_num, bit_val)

    # ------------------------------------------------------------------ #

    def show_running(self):
        self.status_label.setText("Analysis running…")
        self.status_label.setStyleSheet("color: #e0a040; font-style: italic;")
        self.tree.clear()
        self.bit_items.clear()
        self.selectable_bits.clear()

    # ------------------------------------------------------------------ #

    def update_live_bit(self, can_id: str, bit_num: int, value: int):
        key = (can_id, bit_num)
        if key not in self.bit_items:
            return

        item = self.bit_items[key]
        item.setText(2, str(value))
        item.setForeground(
            2, Qt.GlobalColor.green if value else Qt.GlobalColor.red
        )

    # ------------------------------------------------------------------ #

    def apply_deviation_results(self, deviation_dict: dict):
        for event_name, per_id in deviation_dict.items():
            items = self.tree.findItems(
                event_name, Qt.MatchFlag.MatchExactly, 0
            )
            if not items:
                continue

            event_item = items[0]

            for hex_id, score in per_id.items():
                cid = hex_id.replace("0x", "").upper().zfill(4)

                for i in range(event_item.childCount()):
                    id_item = event_item.child(i)
                    if id_item.text(0) != cid:
                        continue

                    id_item.setText(3, f"{score:.3f}")

                    if score <= 1.0:
                        for col in (0, 1, 3, 4):
                            id_item.setForeground(col, Qt.GlobalColor.gray)

                        for j in range(id_item.childCount()):
                            bit_item = id_item.child(j)
                            for col in (0, 1, 3, 4):
                                bit_item.setForeground(col, Qt.GlobalColor.gray)
                    break

        self.status_label.setText("Analysis complete.")
        self.status_label.setStyleSheet("color: #6cc96c; font-style: italic;")

    # ------------------------------------------------------------------ #

    def load_output(self, raw_output: str):
        self.tree.clear()
        self.bit_items.clear()
        self.selectable_bits.clear()

        current_event_item = None

        for line in raw_output.splitlines():
            stripped = line.strip()
            if not stripped or stripped == "Exklusiva bitar per event:":
                continue

            if stripped.endswith(":") and not re.match(r'^[0-9A-Fa-f]{4}:', stripped):
                event_name = stripped[:-1]
                current_event_item = QTreeWidgetItem(
                    self.tree, [event_name, "", "", "", ""]
                )
                current_event_item.setFont(
                    0, QFont("Segoe UI", 9, QFont.Weight.Bold)
                )
                current_event_item.setExpanded(True)
                continue

            id_match = re.match(r'^([0-9A-Fa-f]{4}):\s*(.+)$', stripped)
            if id_match and current_event_item:
                cid = id_match.group(1)
                bits_str = id_match.group(2)

                id_item = QTreeWidgetItem(
                    current_event_item, [cid, "", "", "", ""]
                )
                id_item.setExpanded(True)

                for bit_match in re.finditer(r'b(\d+)\((\d+)\)', bits_str):
                    original_bit = int(bit_match.group(1))
                    changes = bit_match.group(2)

                    byte_index = (original_bit - 1) // 8
                    bit_in_byte = ((original_bit - 1) % 8) + 1
                    reversed_1based = 8 - bit_in_byte + 1
                    bit_num = byte_index * 8 + reversed_1based

                    bit_item = QTreeWidgetItem(
                        id_item,
                        [
                            f"  bit {bit_num}",
                            f"{changes} change(s)",
                            "?",
                            "",
                            "",
                        ]
                    )

                    bit_item.setCheckState(4, Qt.CheckState.Unchecked)

                    self.bit_items[(cid, bit_num)] = bit_item
                    self.selectable_bits[(cid, bit_num)] = bit_item

        self.status_label.setText("Running anomaly detection…")

        self.worker = MLWorker(
            self.settings.baseline_path,
            self.settings.last_export_raw,
            self.settings.last_export_json,
            raw_output,
        )
        self.worker.result_ready.connect(self.apply_deviation_results)
        self.worker.error.connect(self.show_error)
        self.worker.start()

    # ------------------------------------------------------------------ #

    def export_selected_bits(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export selected bits",
            "selected_bits.json",
            "JSON files (*.json)",
        )
        if not path:
            return

        export_data = {}

        for (cid, bit_num), item in self.selectable_bits.items():
            if item.checkState(4) != Qt.CheckState.Checked:
                continue

            id_item = item.parent()
            event_item = id_item.parent()
            event_name = event_item.text(0)

            export_data \
                .setdefault(event_name, {}) \
                .setdefault(cid, []) \
                .append(bit_num)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2)

    # ------------------------------------------------------------------ #

    def show_error(self, message: str):
        self.status_label.setText(f"Error: {message}")
        self.status_label.setStyleSheet("color: red; font-style: italic;")

    def closeEvent(self, event):
        # Reader ownership is external
        super().closeEvent(event)
