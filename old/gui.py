# can_gui.py
# pip install PySide6
from __future__ import annotations

import sys
import csv
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
from enum import Enum

from PySide6 import QtCore, QtGui, QtWidgets


# ---- Original Console Colors mapped to Qt colors ----
class ConsoleColor(Enum):
    RED = "red"
    GREEN = "green"
    BLUE = "blue"
    YELLOW = "yellow"
    RESET = "reset"


def color_to_qcolor(c: ConsoleColor) -> Optional[QtGui.QColor]:
    if c == ConsoleColor.RED:
        return QtGui.QColor("#D32F2F")
    if c == ConsoleColor.GREEN:
        return QtGui.QColor("#388E3C")
    if c == ConsoleColor.BLUE:
        return QtGui.QColor("#1976D2")
    if c == ConsoleColor.YELLOW:
        return QtGui.QColor("#F9A825")
    return None  # RESET: default color (let the view decide)


# ---- Domain Data ----
@dataclass
class CANFrame:
    time_stamp: int
    id: int
    ext: str
    dir: str
    bus: int
    cnt: int
    length: int
    # Up to 8 bytes; each item is (value, color). Value can be None if not present.
    bytes: List[Tuple[Optional[int], ConsoleColor]]


# ---- CSV Reading (robust to short rows / missing D*) ----
def read_data_file(filename: str, frame_count: int) -> Dict[int, CANFrame]:
    """
    Reads up to frame_count frames and aggregates by ID.
    For each ID, we keep the latest timestamp and the latest bytes,
    incrementing the count each time we see the ID again.
    """
    result: Dict[int, CANFrame] = {}
    frames_read: int = 0

    def parse_hex_field(s: str) -> Optional[int]:
        """Parse a hex string like '0A' or '' -> int or None, safely."""
        if s is None:
            return None
        s = s.strip()
        if not s:
            return None
        try:
            return int(s, 16)
        except ValueError:
            return None

    with open(filename, mode="r", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            if frames_read >= frame_count:
                break

            # Required fields (with defensive parsing)
            try:
                time_stamp = int(row.get("Time Stamp", "0"))
            except ValueError:
                time_stamp = 0

            # ID can be hex like "18FF50E5" or "0x18FF50E5"
            raw_id = row.get("ID", "0")
            raw_id = raw_id.strip().lower()
            if raw_id.startswith("0x"):
                raw_id = raw_id[2:]
            try:
                arb_id = int(raw_id, 16)
            except ValueError:
                arb_id = 0

            extended = row.get("Extended", "")  # keep as string (e.g., '0'/'1' or 'True'/'False')
            direction = row.get("Dir", "")
            try:
                bus = int(row.get("Bus", "0"))
            except ValueError:
                bus = 0
            try:
                length = int(row.get("LEN", "0"))
            except ValueError:
                length = 0
            length = max(0, min(8, length))  # clamp to [0..8] for CAN classic

            # Read D1..D8 (or up to 'length')
            byte_list: List[Tuple[Optional[int], ConsoleColor]] = []
            for i in range(1, 9):  # Always normalize to 8 slots for the GUI
                if i <= length:
                    v = parse_hex_field(row.get(f"D{i}", ""))
                    byte_list.append((v, ConsoleColor.RESET))
                else:
                    byte_list.append((None, ConsoleColor.RESET))

            if arb_id in result:
                fr = result[arb_id]
                fr.time_stamp = time_stamp
                # fr.id remains the same (bugfix from original code)
                fr.ext = extended
                fr.dir = direction
                fr.bus = bus
                fr.cnt += 1
                fr.length = length
                fr.bytes = byte_list
            else:
                result[arb_id] = CANFrame(
                    time_stamp=time_stamp,
                    id=arb_id,
                    ext=extended,
                    dir=direction,
                    bus=bus,
                    cnt=1,
                    length=length,
                    bytes=byte_list,
                )

            frames_read += 1

    return result


# ---- Snapshot comparison logic (preserved from your script) ----
def compute_snapshot_result(
    s1: Dict[int, CANFrame],
    s2: Dict[int, CANFrame],
    s3: Dict[int, CANFrame],
) -> Dict[int, CANFrame]:
    """
    Replicates your print snapshot logic but returns the colored result dict.
    """
    result: Dict[int, CANFrame] = {}

    # Base = s2 (latest state for existing IDs)
    for key, value in s2.items():
        # Make a shallow copy to avoid mutating original structures
        result[key] = CANFrame(
            time_stamp=value.time_stamp,
            id=value.id,
            ext=value.ext,
            dir=value.dir,
            bus=value.bus,
            cnt=value.cnt,
            length=value.length,
            bytes=[(b, c) for (b, c) in value.bytes],
        )

        # Detect noise between s1 and s2: color RED where bytes differ
        if key in s1:
            s1_bytes = s1[key].bytes
            for index, b2 in enumerate(value.bytes):
                b1 = s1_bytes[index] if index < len(s1_bytes) else (None, ConsoleColor.RESET)
                if b2[0] != b1[0]:
                    result[key].bytes[index] = (b2[0], ConsoleColor.RED)

    # Now handle s3
    for key, value in s3.items():
        if key not in s2:
            # New ID in s3 -> color all bytes YELLOW
            result[key] = CANFrame(
                time_stamp=value.time_stamp,
                id=value.id,
                ext=value.ext,
                dir=value.dir,
                bus=value.bus,
                cnt=value.cnt,
                length=value.length,
                bytes=[(b, ConsoleColor.YELLOW) for (b, _) in value.bytes],
            )
        else:
            # Byte changes between s2 and s3 (but don't overwrite RED)
            s2_bytes = s2[key].bytes
            for index, b3 in enumerate(value.bytes):
                if result[key].bytes[index][1] != ConsoleColor.RESET:
                    continue
                b2 = s2_bytes[index] if index < len(s2_bytes) else (None, ConsoleColor.RESET)
                if b3[0] != b2[0]:
                    result[key].bytes[index] = (b3[0], ConsoleColor.BLUE)

    return result


# ---- Qt Table Model ----
class CanTableModel(QtCore.QAbstractTableModel):
    BASE_HEADERS = ["#", "Time", "ID", "Ext", "Dir", "Bus", "Cnt", "Len"]
    BYTE_HEADERS = [f"D{i}" for i in range(1, 9)]
    HEADERS = BASE_HEADERS + BYTE_HEADERS

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: List[CANFrame] = []

    def set_frames(self, frames: List[CANFrame]):
        self.beginResetModel()
        self._rows = frames
        self.endResetModel()

    def rowCount(self, parent=QtCore.QModelIndex()) -> int:
        return len(self._rows)

    def columnCount(self, parent=QtCore.QModelIndex()) -> int:
        return len(self.HEADERS)

    def headerData(self, section: int, orientation: QtCore.Qt.Orientation, role: int = QtCore.Qt.DisplayRole):
        if role == QtCore.Qt.DisplayRole and orientation == QtCore.Qt.Horizontal:
            return self.HEADERS[section]
        return super().headerData(section, orientation, role)

    def data(self, index: QtCore.QModelIndex, role: int = QtCore.Qt.DisplayRole):
        if not index.isValid():
            return None
        r, c = index.row(), index.column()
        fr = self._rows[r]

        # DisplayRole
        if role == QtCore.Qt.DisplayRole:
            if c == 0:
                return r + 1
            elif c == 1:
                return fr.time_stamp
            elif c == 2:
                return f"0x{fr.id:03X}"
            elif c == 3:
                return fr.ext
            elif c == 4:
                return fr.dir
            elif c == 5:
                return fr.bus
            elif c == 6:
                return fr.cnt
            elif c == 7:
                return fr.length
            else:
                # Byte columns D1..D8
                bi = c - len(self.BASE_HEADERS)  # 0..7
                if 0 <= bi < 8:
                    v, _ = fr.bytes[bi]
                    return "" if v is None else f"{v:02X}"
        # ForegroundRole (color bytes)
        if role == QtCore.Qt.ForegroundRole:
            if c >= len(self.BASE_HEADERS):
                bi = c - len(self.BASE_HEADERS)
                v, col = fr.bytes[bi]
                qc = color_to_qcolor(col)
                if qc is not None and v is not None:
                    return QtGui.QBrush(qc)

        # Monospace font for bytes
        if role == QtCore.Qt.FontRole:
            if c >= len(self.BASE_HEADERS):
                f = QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.FixedFont)
                f.setPointSize(f.pointSize() + 0)  # adjust if desired
                return f

        return None

    def sort(self, column: int, order: QtCore.Qt.SortOrder = QtCore.Qt.AscendingOrder) -> None:
        reverse = (order == QtCore.Qt.DescendingOrder)
        self.layoutAboutToBeChanged.emit()
        if column == 0:
            # row index: keep natural order or reverse
            self._rows = list(reversed(self._rows)) if reverse else self._rows
        elif column == 1:
            self._rows.sort(key=lambda x: x.time_stamp, reverse=reverse)
        elif column == 2:
            self._rows.sort(key=lambda x: x.id, reverse=reverse)
        elif column == 5:
            self._rows.sort(key=lambda x: x.bus, reverse=reverse)
        elif column == 6:
            self._rows.sort(key=lambda x: x.cnt, reverse=reverse)
        elif column == 7:
            self._rows.sort(key=lambda x: x.length, reverse=reverse)
        else:
            # sort by byte column (treat None as -1)
            if column >= len(self.BASE_HEADERS):
                bi = column - len(self.BASE_HEADERS)
                self._rows.sort(key=lambda x: -1 if x.bytes[bi][0] is None else x.bytes[bi][0], reverse=reverse)
        self.layoutChanged.emit()


# ---- Main Window ----
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CAN Snapshot Viewer (PySide6)")
        self.resize(1200, 700)

        self.table = QtWidgets.QTableView(self)
        self.model = CanTableModel(self)
        self.table.setModel(self.model)
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        self.table.verticalHeader().setDefaultSectionSize(22)
        self.setCentralWidget(self.table)

        self.statusBar().showMessage("Ready")

        # Toolbar
        tb = self.addToolBar("Main")
        open_act = QtGui.QAction("Open CSV…", self)
        open_act.triggered.connect(self.open_csv)
        tb.addAction(open_act)

        reload_act = QtGui.QAction("Reload", self)
        reload_act.triggered.connect(self.reload_current)
        tb.addAction(reload_act)

        # Defaults
        self.current_file = "data.csv"
        self.s1_frames = 500
        self.s2_frames = 51000
        self.s3_frames = 52000

        # Attempt initial load (if data.csv exists)
        try:
            self.load_and_show(self.current_file)
        except Exception as e:
            self.statusBar().showMessage(f"Open a CSV to begin — {e}")

    def open_csv(self):
        file, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open CAN CSV", ".", "CSV Files (*.csv);;All Files (*)"
        )
        if file:
            self.current_file = file
            self.load_and_show(file)

    def reload_current(self):
        if self.current_file:
            self.load_and_show(self.current_file)

    def load_and_show(self, filename: str):
        # Read three snapshots (like your original code)
        s1 = read_data_file(filename, self.s1_frames)
        s2 = read_data_file(filename, self.s2_frames)
        s3 = read_data_file(filename, self.s3_frames)

        result = compute_snapshot_result(s1, s2, s3)

        # Turn dict into sorted list by ID for display
        frames_sorted = [result[k] for k in sorted(result.keys())]

        self.model.set_frames(frames_sorted)
        self.statusBar().showMessage(
            f"Loaded {filename} | s1={len(s1)} IDs, s2={len(s2)} IDs, s3={len(s3)} IDs, result={len(result)} IDs"
        )


def main():
    app = QtWidgets.QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()