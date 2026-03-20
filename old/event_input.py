from __future__ import annotations
import sys, json
from pathlib import Path
from typing import List, Dict, Optional
from PySide6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QDialogButtonBox, QMessageBox
)

def _to_float(item: Optional[QTableWidgetItem]) -> Optional[float]:
    try:
        return float((item.text() if item else "").strip())
    except Exception:
        return None

class EventDialog(QDialog):
    def __init__(self, csv_path: Path, load_existing: bool):
        super().__init__()
        self.setWindowTitle("Events (sekunder)")
        self.csv_path = csv_path
        self.events_path = csv_path.with_suffix(".events.json")

        v = QVBoxLayout(self)
        self.table = QTableWidget(0, 3, self)
        self.table.setHorizontalHeaderLabels(["Event", "Start (s)", "Slut (s)"])
        v.addWidget(self.table)

        rowbtn = QHBoxLayout()
        addb = QPushButton("+ Lägg till")
        remvb = QPushButton("− Ta bort")
        addb.clicked.connect(self.add_row)
        remvb.clicked.connect(self.rem_row)
        rowbtn.addWidget(addb)
        rowbtn.addWidget(remvb)
        v.addLayout(rowbtn)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.on_accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)

        if load_existing and self.events_path.exists():
            try:
                events = json.loads(self.events_path.read_text(encoding="utf-8"))
                for i, ev in enumerate(events):
                    self.add_row()
                    self.table.setItem(i, 0, QTableWidgetItem(str(ev.get("name", f"Event {i+1}"))))
                    self.table.setItem(i, 1, QTableWidgetItem(str(ev.get("start_s", ""))))
                    self.table.setItem(i, 2, QTableWidgetItem(str(ev.get("end_s", ""))))
            except Exception:
                self.add_row()
        else:
            self.add_row()

    def add_row(self):
        r = self.table.rowCount()
        self.table.insertRow(r)
        if not self.table.item(r, 0):
            self.table.setItem(r, 0, QTableWidgetItem(f"Event {r+1}"))
        if not self.table.item(r, 1):
            self.table.setItem(r, 1, QTableWidgetItem(""))
        if not self.table.item(r, 2):
            self.table.setItem(r, 2, QTableWidgetItem(""))

    def rem_row(self):
        r = self.table.currentRow()
        if r >= 0:
            self.table.removeRow(r)

    def on_accept(self):
        try:
            events: List[Dict] = []
            for r in range(self.table.rowCount()):
                name_it = self.table.item(r, 0)
                s_it = self.table.item(r, 1)
                e_it = self.table.item(r, 2)
                name = (name_it.text().strip() if name_it else "").strip() or f"Event {r+1}"
                s = _to_float(s_it)
                e = _to_float(e_it)
                if s is None or e is None:
                    raise ValueError(f"Rad {r+1}: ogiltig start/slut")
                if e < s:
                    raise ValueError(f"Rad {r+1}: slut < start")
                events.append({"name": name, "start_s": s, "end_s": e})

            self.events_path.write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")
            self.accept()
        except Exception as ex:
            QMessageBox.critical(self, "Fel", str(ex))

def main():
    if len(sys.argv) < 2:
        print("Usage: python event_input.py <converted.csv> [--edit|--new]")
        sys.exit(1)
    csv_path = Path(sys.argv[1])
    mode = sys.argv[2] if len(sys.argv) >= 3 else ""
    load_existing = (mode == "--edit") or (mode == "" and csv_path.with_suffix(".events.json").exists())

    app = QApplication(sys.argv)
    dlg = EventDialog(csv_path, load_existing=load_existing)
    sys.exit(dlg.exec())

if __name__ == "__main__":
    main()
