# read_can_gui_6.py
from __future__ import annotations

from dataclasses import dataclass
import sys, subprocess, csv, json, shutil
from typing import Dict, List, Optional, Tuple
from pathlib import Path

import can
from can import BusABC, Message
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QBrush, QCloseEvent, QColor
from PySide6.QtWidgets import (
    QApplication, QDockWidget, QLabel, QMainWindow, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget, QDialog, QVBoxLayout as QVBL,
    QHBoxLayout as QHBL, QRadioButton, QComboBox, QFileDialog, QMessageBox,
    QDialogButtonBox, QTabWidget, QLabel as QLabelW
)

# CAN config
CAN_INTERFACE = "slcan"
CAN_CHANNEL   = "COM9"
CAN_BITRATE   = 500_000

BASE_DIR = Path(__file__).parent
SAVED_DIR = BASE_DIR / "saved_recordings_csv"   # CSV hamnar här
RAW_DIR   = BASE_DIR / "raw_recordnings"        # TRC oförändrad
SAVED_DIR.mkdir(exist_ok=True)
RAW_DIR.mkdir(exist_ok=True)

# --- StartDialog (only this class) ---
class StartDialog(QDialog):
    """
    Live: Run alltid aktiv.
    Inspelning: Run aktiv först när en inspelningsfil är vald (via lista eller upload).
    """
    class DropArea(QLabel):
        def __init__(self, on_file):
            super().__init__("Dra & släpp .csv eller .trc här")
            self.setAlignment(Qt.AlignCenter)
            self.setStyleSheet("QLabel{border:2px dashed #888; padding:16px; border-radius:6px; color:#bbb;}")
            self.setAcceptDrops(True); self.on_file = on_file
        def _ok(self, e):
            if not e.mimeData().hasUrls(): return False
            return any(u.isLocalFile() and Path(u.toLocalFile()).suffix.lower() in (".csv",".trc") for u in e.mimeData().urls())
        def dragEnterEvent(self, e): e.acceptProposedAction() if self._ok(e) else e.ignore()
        def dragMoveEvent (self, e): e.acceptProposedAction() if self._ok(e) else e.ignore()
        def dropEvent     (self, e):
            for u in e.mimeData().urls():
                p = Path(u.toLocalFile())
                if p.suffix.lower() in (".csv",".trc"): self.on_file(p); break

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Välj läge")
        self.mode: str = "Live"
        self.csv_path: Optional[Path] = None

        root = QVBL(self)

        # ---- Rad 1: Läge (ALLTID synlig) ----
        self.top_row = QWidget(self); top_l = QHBL(self.top_row)
        self.rb_live = QRadioButton("Live"); self.rb_rec  = QRadioButton("Inspelning")
        self.rb_live.setChecked(True)
        top_l.addWidget(self.rb_live); top_l.addWidget(self.rb_rec); top_l.addStretch(1)
        root.addWidget(self.top_row)

        # ---- Sektion: Källa (bara när Inspelning) ----
        self.source_section = QWidget(self); src_v = QVBL(self.source_section)

        # a) Sparade inspelningar
        saved_row = QWidget(self.source_section); saved_h = QHBL(saved_row)
        saved_h.addWidget(QLabel("Sparade inspelningar:"))
        self.saved_combo = QComboBox(saved_row)
        self._refresh_saved()
        self.saved_combo.currentIndexChanged.connect(self._on_saved_selected)
        saved_h.addWidget(self.saved_combo, 1)
        src_v.addWidget(saved_row)

        # b) Ladda upp
        upload_row = QWidget(self.source_section); upload_v = QVBL(upload_row)
        upload_v.addWidget(QLabel("Ladda upp:"))
        self.drop = StartDialog.DropArea(self._handle_file)
        self.btn_browse = QPushButton("Bläddra på den här datorn…"); self.btn_browse.clicked.connect(self._browse)
        upload_v.addWidget(self.drop); upload_v.addWidget(self.btn_browse, alignment=Qt.AlignRight)
        src_v.addWidget(upload_row)

        root.addWidget(self.source_section)

        # ---- Run/Cancel (centrerad, alltid synlig) ----
        self.btn_row = QWidget(self); btn_l = QHBL(self.btn_row)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.run_btn    = bb.button(QDialogButtonBox.Ok);     self.run_btn.setText("Run")
        self.cancel_btn = bb.button(QDialogButtonBox.Cancel); self.cancel_btn.setText("Cancel")
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        btn_l.addStretch(1); btn_l.addWidget(bb); btn_l.addStretch(1)
        root.addWidget(self.btn_row)

        # wiring
        self.rb_live.toggled.connect(self._toggle_ui)
        self.rb_rec .toggled.connect(self._toggle_ui)
        self._toggle_ui()            # init UI visibility
        self._update_run_enabled()   # init Run state

    # -------- helpers --------
    def _refresh_saved(self) -> None:
        self.saved_combo.clear()
        self.saved_combo.addItem("— Välj inspelning —", userData=None)  # placeholder index 0
        self.saved_combo.addItems([p.name for p in sorted(SAVED_DIR.glob("*.csv"))])
        self.saved_combo.setCurrentIndex(0)

    def _toggle_ui(self) -> None:
        live = self.rb_live.isChecked()
        self.source_section.setVisible(not live)
        self._update_run_enabled()

    def _has_selected_recording(self) -> bool:
        """True om vi har en giltig csv_path ELLER listval != placeholder."""
        if self.csv_path and self.csv_path.exists(): return True
        return self.saved_combo.currentIndex() > 0

    def _update_run_enabled(self) -> None:
        """Live: Run enabled. Inspelning: Run enabled endast om fil vald."""
        live = self.rb_live.isChecked()
        self.run_btn.setEnabled(True if live else self._has_selected_recording())

    def _on_saved_selected(self, idx: int) -> None:
        if idx > 0:
            name = self.saved_combo.itemText(idx).strip()
            if name:
                self.csv_path = SAVED_DIR / name
                self.rb_rec.setChecked(True)  # säkerställ Inspelning
                self._ask_events(self.csv_path)
        self._update_run_enabled()

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Välj fil", str(BASE_DIR), "CSV/TRC (*.csv *.trc)")
        if path: self._handle_file(Path(path))

    def _handle_file(self, src: Path) -> None:
        try:
            self.rb_rec.setChecked(True)  # Inspelning
            if src.suffix.lower() == ".trc":
                dest_trc = RAW_DIR / src.name
                if dest_trc.resolve() != src.resolve(): shutil.copy2(src, dest_trc)
                dest_csv = SAVED_DIR / (src.stem + ".csv")
                csv_path = self._convert_trc_to_csv(dest_trc, dest_csv)
                if not csv_path: return
                self.csv_path = csv_path
                self._refresh_saved()
                self._ask_events(csv_path)
            elif src.suffix.lower() == ".csv":
                dest_csv = SAVED_DIR / src.name
                if dest_csv.resolve() != src.resolve(): shutil.copy2(src, dest_csv)
                self.csv_path = dest_csv
                self._refresh_saved()
                self._ask_events(dest_csv)
        except Exception as e:
            QMessageBox.critical(self, "Fel vid filhantering", str(e))
        finally:
            self._update_run_enabled()

    def _convert_trc_to_csv(self, trc_in: Path, csv_out: Path) -> Optional[Path]:
        try:
            script = BASE_DIR / "trc_to_csv.py"
            subprocess.run([sys.executable, str(script), str(trc_in), str(csv_out)],
                           check=True, capture_output=True, text=True)
            return csv_out if csv_out.exists() else None
        except Exception as e:
            QMessageBox.critical(self, "TRC->CSV fel", str(e)); return None

    def _ask_events(self, csv_path: Path) -> None:
        ev_script = BASE_DIR / "event_input.py"
        if not ev_script.exists():
            alt = BASE_DIR / "even_input.py"
            if alt.exists(): ev_script = alt
        ev_path = csv_path.with_suffix(".events.json")
        if ev_path.exists():
            mb = QMessageBox(self); mb.setWindowTitle("Events")
            mb.setText("Befintliga events hittades. Välj alternativ:")
            use_btn  = mb.addButton("Använd befintliga", QMessageBox.AcceptRole)
            edit_btn = mb.addButton("Redigera befintliga", QMessageBox.ActionRole)
            new_btn  = mb.addButton("Rapportera nya", QMessageBox.DestructiveRole)
            cancel   = mb.addButton(QMessageBox.Cancel)
            mb.exec()
            clicked = mb.clickedButton()
            if clicked is use_btn:
                self._compute_and_show_ranges(csv_path)
            elif clicked is edit_btn:
                try: subprocess.run([sys.executable, str(ev_script), str(csv_path), "--edit"], check=True)
                except Exception as e: QMessageBox.critical(self, "Event-fel", str(e)); return
                self._compute_and_show_ranges(csv_path)
            elif clicked is new_btn:
                try: subprocess.run([sys.executable, str(ev_script), str(csv_path), "--new"], check=True)
                except Exception as e: QMessageBox.critical(self, "Event-fel", str(e)); return
                self._compute_and_show_ranges(csv_path)
        else:
            if QMessageBox.question(self, "Events", "Inga events. Vill du rapportera nya nu?",
                                    QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
                try: subprocess.run([sys.executable, str(ev_script), str(csv_path), "--new"], check=True)
                except Exception as e: QMessageBox.critical(self, "Event-fel", str(e)); return
                self._compute_and_show_ranges(csv_path)

    # ---- ranges (ms tas ej med i visning) ----
    def _load_index(self, csv_path: Path) -> List[Tuple[int, float]]:
        idx: List[Tuple[int, float]] = []
        with csv_path.open(newline="", encoding="utf-8") as f:
            r = csv.DictReader(f)
            for row in r:
                try: idx.append((int(row["Message Number"]), float(row["Time Offset (ms)"])))
                except: pass
        if not idx: raise ValueError("Kunde inte läsa index från CSV.")
        return idx
    def _nearest_msg(self, index: List[Tuple[int, float]], target_ms: float) -> int:
        return int(min(index, key=lambda nt: abs(nt[1] - target_ms))[0])
    def _compute_and_show_ranges(self, csv_path: Path) -> None:
        ev_path = csv_path.with_suffix(".events.json")
        if not ev_path.exists(): return
        try:
            events = json.loads(ev_path.read_text(encoding="utf-8"))
            index = self._load_index(csv_path)
            lines = []
            for ev in events:
                s_ms = (float(ev["start_s"]) - 2.0) * 1000.0
                e_ms = (float(ev["end_s"]) + 2.0) * 1000.0
                lines.append(f"{ev.get('name','Event')}: {self._nearest_msg(index, s_ms)}–{self._nearest_msg(index, e_ms)}")
            if lines: QMessageBox.information(self, "Search ranges", "\n".join(lines))
        except Exception as e:
            QMessageBox.critical(self, "Event/Range-fel", str(e))

    # ---- resultat ----
    def get_choice(self) -> Tuple[str, Optional[Path]]:
        self.mode = "Live" if self.rb_live.isChecked() else "Inspelning"
        if self.mode == "Inspelning" and (self.csv_path is None or not self.csv_path.exists()):
            if self.saved_combo.currentIndex() > 0:
                name = self.saved_combo.currentText().strip()
                self.csv_path = (SAVED_DIR / name) if name else None
        return self.mode, self.csv_path

# -------------------- CAN live-läsare --------------------
class CanReader(QThread):
    msg_signal: Signal = Signal(object)
    def __init__(self) -> None:
        super().__init__()
        self.running: bool = True
    def run(self) -> None:
        try:
            bus: BusABC = can.Bus(interface=CAN_INTERFACE, channel=CAN_CHANNEL, bitrate=CAN_BITRATE)
        except Exception as e:
            print("Failed to open CAN:", e); return
        while self.running:
            msg: Optional[Message] = bus.recv(0.5)
            if msg is not None: self.msg_signal.emit(msg)
    def stop(self) -> None:
        self.running = False

class InspectorWidget(QWidget):
    def __init__(self, main_window: "MainWindow"):
        super().__init__()
        self.main_window = main_window
        layout = QVBoxLayout()
        self.elapsed_time_label = QLabel("Elapsed time: 0 s")
        layout.addWidget(self.elapsed_time_label)
        self.clear_button = QPushButton("Clear"); self.clear_button.clicked.connect(self.clear); layout.addWidget(self.clear_button)
        self.noise1_button = QPushButton("Start noise calc"); self.noise1_button.clicked.connect(self.noise1); layout.addWidget(self.noise1_button)
        self.noise2_button = QPushButton("Start identify calc"); self.noise2_button.clicked.connect(self.noise2); layout.addWidget(self.noise2_button)
        layout.addStretch(); self.setLayout(layout)

    def clear(self) -> None:
        self.main_window.clear_noise1(); self.main_window.clear_noise2()
        self.main_window.table.setRowCount(0); self.main_window.can_frames.clear()
        self.main_window.initial_timestamp = 0.0
        self.elapsed_time_label.setText("Elapsed time: 0 s")

    def noise1(self) -> None:
        mw = self.main_window; mw.running_noise1 = not mw.running_noise1
        self.noise1_button.setText("Stop noise calc" if mw.running_noise1 else "Start noise calc")
        if mw.running_noise1: mw.clear_noise1()

    def noise2(self) -> None:
        mw = self.main_window; mw.running_noise2 = not mw.running_noise2
        self.noise2_button.setText("Stop identify calc" if mw.running_noise2 else "Start identify calc")
        if mw.running_noise2: mw.clear_noise2()

@dataclass
class CANFrame:
    row: int; noise1: List[bool]; noise2: List[bool]
    time: float; ext: bool; cnt: int; len: int; data: bytearray

class MainWindow(QMainWindow):
    def __init__(self, start_live: bool = True, recording_csv: Optional[Path] = None) -> None:
        super().__init__()
        self.setWindowTitle("CAN Scrape")

        self.can_frames: Dict[int, CANFrame] = {}
        self.running_noise1: bool = False
        self.running_noise2: bool = False
        self.initial_timestamp: float = 0.0

        self.table: QTableWidget = QTableWidget(0, 14)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setHorizontalHeaderLabels(
            ["Time Stamp", "ID", "Extended", "Count", "Length",
             "D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8", "Bits (64)"]
        )
        self.table.resizeColumnsToContents()
        self.setCentralWidget(self.table)

        self.reader: Optional[CanReader] = CanReader()
        self.reader.msg_signal.connect(self.update_table)
        if start_live:
            self.reader.start()

        self.inspector = InspectorWidget(self)
        dock = QDockWidget("Inspector", self)
        dock.setWidget(self.inspector)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)

        if recording_csv:
            self.setWindowTitle(f"CAN Scrape – Inspelning: {recording_csv.name}")

    def update_table(self, msg: Message) -> None:
        can_id: int = msg.arbitration_id
        if self.initial_timestamp <= 0.0:
            self.initial_timestamp = msg.timestamp
        self.inspector.elapsed_time_label.setText(f"Elapsed time: {msg.timestamp - self.initial_timestamp:.1f} s")

        if can_id in self.can_frames:
            row = self.can_frames[can_id].row
            count = self.can_frames[can_id].cnt + 1
            if self.running_noise1:
                for i, b in enumerate(self.can_frames[can_id].data):
                    if msg.data[i] != b: self.can_frames[can_id].noise1[i] = True
            if self.running_noise2:
                for i, b in enumerate(self.can_frames[can_id].data):
                    if msg.data[i] != b: self.can_frames[can_id].noise2[i] = True
            cf = self.can_frames[can_id]
            cf.time = msg.timestamp; cf.ext = msg.is_extended_id
            cf.cnt = count; cf.len = msg.dlc; cf.data = msg.data
        else:
            row = self.table.rowCount(); count = 1
            self.can_frames[can_id] = CANFrame(row, [False]*msg.dlc, [False]*msg.dlc, msg.timestamp, msg.is_extended_id, count, msg.dlc, msg.data)
            self.table.insertRow(row)

        self.table.setItem(row, 0, QTableWidgetItem(f"{msg.timestamp:.0f}"))
        self.table.setItem(row, 1, QTableWidgetItem(f"{can_id:03X}"))
        self.table.setItem(row, 2, QTableWidgetItem(str(msg.is_extended_id)))
        self.table.setItem(row, 3, QTableWidgetItem(str(self.can_frames[can_id].cnt)))
        self.table.setItem(row, 4, QTableWidgetItem(str(msg.dlc)))

        for i in range(min(len(msg.data), 8)):
            it = QTableWidgetItem(f"{msg.data[i]:02X}")
            if self.can_frames[can_id].noise1[i]: it.setForeground(QBrush(QColor("red")))
            elif self.can_frames[can_id].noise2[i]: it.setForeground(QBrush(QColor("blue")))
            self.table.setItem(row, i + 5, it)

        bit_string = "".join(f"{byte:08b} " for byte in msg.data[:8])
        self.table.setItem(row, 13, QTableWidgetItem(bit_string))

    def closeEvent(self, event: QCloseEvent) -> None:
        if isinstance(self.reader, CanReader):
            self.reader.stop(); self.reader.wait()
        super().closeEvent(event)

    def compare_data(self, old_data: bytearray, new_data: bytearray) -> List[bool]:
        changed_bits: List[bool] = [False]*64
        for bi in range(8):
            xor_value = old_data[bi] ^ new_data[bi]
            for bj in range(8):
                absolute_bit = bi*8 + (7 - bj)
                changed_bits[absolute_bit] = bool(xor_value & (1 << bj))
        return changed_bits

    def clear_noise1(self) -> None:
        for cf in self.can_frames.values(): cf.noise1 = [False]*cf.len
    def clear_noise2(self) -> None:
        for cf in self.can_frames.values(): cf.noise2 = [False]*cf.len


if __name__ == "__main__":
    app: QApplication = QApplication(sys.argv)
    dlg = StartDialog()
    if dlg.exec() != QDialog.Accepted:
        sys.exit(0)
    mode, csv_path = dlg.get_choice()
    window = MainWindow(start_live=(mode=="Live"), recording_csv=csv_path if mode!="Live" else None)
    window.resize(960, 540)
    window.show()
    sys.exit(app.exec())
