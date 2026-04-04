import re

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QLabel, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget
)


class AnalysisResultWidget(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        self.status_label = QLabel("No analysis run yet.")
        self.status_label.setStyleSheet("color: #888; font-style: italic;")
        layout.addWidget(self.status_label)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Event / ID", "Bits (changes)"])
        self.tree.setColumnWidth(0, 260)
        self.tree.setAlternatingRowColors(True)
        self.tree.setEditTriggers(QTreeWidget.EditTrigger.NoEditTriggers)
        self.tree.setFont(QFont("Consolas", 9))
        layout.addWidget(self.tree)

    # ------------------------------------------------------------------ #

    def show_running(self):
        self.status_label.setText("Analysis running…")
        self.status_label.setStyleSheet("color: #e0a040; font-style: italic;")
        self.tree.clear()

    def show_error(self, message: str):
        self.status_label.setText(f"Error: {message}")
        self.status_label.setStyleSheet("color: #e06060; font-style: italic;")

    def load_output(self, raw_output: str):
        """Parsar stdout från event-bits/main.py och fyller trädet."""
        self.tree.clear()

        # Format:
        #   Exklusiva bitar per event:
        #
        #     Drivers door:
        #       00C3: b5(4), b12(4)
        #       ...
        #     Inga exklusiva bitar

        current_event_item: QTreeWidgetItem | None = None

        for line in raw_output.splitlines():
            stripped = line.strip()
            if not stripped or stripped == "Exklusiva bitar per event:":
                continue

            # Event-rubrik: slutar med ":" och innehåller inget ":" efter det
            if stripped.endswith(":") and not re.match(r'^[0-9A-Fa-f]{4}:', stripped):
                event_name = stripped[:-1]
                current_event_item = QTreeWidgetItem(self.tree, [event_name, ""])
                current_event_item.setFont(0, QFont("Segoe UI", 9, QFont.Weight.Bold))
                current_event_item.setExpanded(True)
                continue

            if stripped == "Inga exklusiva bitar":
                if current_event_item:
                    child = QTreeWidgetItem(current_event_item, ["—", "no exclusive bits"])
                    child.setForeground(0, Qt.GlobalColor.gray)
                    child.setForeground(1, Qt.GlobalColor.gray)
                continue

            # ID-rad: "00C3: b5(4), b12(4)"
            id_match = re.match(r'^([0-9A-Fa-f]{4}):\s*(.+)$', stripped)
            if id_match and current_event_item:
                can_id   = id_match.group(1)
                bits_str = id_match.group(2)

                id_item = QTreeWidgetItem(current_event_item, [can_id, ""])
                id_item.setExpanded(True)

                # Lägg också till varje bit som eget barn
                for bit_match in re.finditer(r'b(\d+)\((\d+)\)', bits_str):
                    bit_num = bit_match.group(1)
                    changes = bit_match.group(2)
                    QTreeWidgetItem(id_item, [f"  bit {bit_num}", f"{changes} change(s)"])

        if self.tree.topLevelItemCount() == 0:
            self.status_label.setText("Analysis complete — no results.")
            self.status_label.setStyleSheet("color: #888; font-style: italic;")
        else:
            self.status_label.setText("Analysis complete.")
            self.status_label.setStyleSheet("color: #6cc96c; font-style: italic;")