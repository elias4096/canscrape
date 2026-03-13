import sys
import csv
from dataclasses import dataclass
from typing import List, Dict, Tuple

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QLabel,
    QPushButton,
    QSpinBox,
    QMessageBox,
    QFrame,
)


DATA_FILE = "data.csv"


@dataclass
class CANFrame:
    time: int
    id: int
    ext: str
    dir: str
    bus: int
    cnt: int
    len: int
    data: List[int]


def read_data_file(filename: str) -> List[CANFrame]:
    frames: List[CANFrame] = []

    with open(filename, mode="r", newline="") as f:
        reader = csv.DictReader(f)

        for row in reader:
            try:
                # Time as integer (supports "123" or "123.456" -> 123)
                raw_ts = (row.get("Time Stamp", "") or "").strip()
                ts = int(float(raw_ts)) if raw_ts else 0

                raw_id = (row.get("ID", "") or "").strip()
                can_id = int(raw_id, 16) if raw_id else 0

                ext = (row.get("Extended", "") or "").strip()  # keep "Yes"/"No" as-is
                direction = (row.get("Dir", "") or "").strip()
                bus = int((row.get("Bus", "0") or "0").strip())

                length = int((row.get("LEN", "0") or "0").strip())
                length = max(0, min(length, 8))  # clamp to 0..8

                # Parse D1..D8 as hex; blanks become 0
                bytes_all: List[int] = []
                for i in range(1, 9):
                    v = (row.get(f"D{i}", "") or "").strip()
                    bytes_all.append(int(v, 16) if v else 0)

                data = bytes_all[:length]

                frames.append(
                    CANFrame(
                        time=ts,
                        id=can_id,
                        ext=ext,
                        dir=direction,
                        bus=bus,
                        cnt=1,          # each raw CSV row starts at 1
                        len=length,
                        data=data,
                    )
                )

            except Exception:
                # Skip malformed rows safely
                continue

    return frames


class DataTab(QWidget):
    HEADERS = [
        "Time Stamp", "ID", "Extended", "Dir", "Bus", "CNT", "LEN",
        "D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8"
    ]

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)

        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setColumnCount(len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)

        layout.addWidget(self.table)

        # Playback state
        self.frames: List[CANFrame] = []
        self.next_index = 0
        self.delay_ms = 10

        # Dict-based upsert state: key -> (row_index, cnt)
        self.rows: Dict[Tuple, Tuple[int, int]] = {}

        # Timer for streaming frames
        self.timer = QTimer(self)
        self.timer.setInterval(self.delay_ms)
        self.timer.timeout.connect(self._on_tick)

    # -------- Public API --------
    def load_frames(self, frames: List[CANFrame]):
        self.frames = frames
        self.reset_table()

    def play(self):
        """Start or resume playback from current next_index."""
        if self.frames and not self.timer.isActive():
            if self.next_index >= len(self.frames):
                self.next_index = 0
            self.timer.start()

    def stop(self):
        """Stop playback and mark as finished."""
        self.timer.stop()
        self.next_index = len(self.frames)

    def restart(self):
        """Clear the table and play from the beginning of the same frames list."""
        self.reset_table()
        self.play()

    def reset_table(self):
        """Clear table and internal mapping; keep frames list untouched."""
        self.timer.stop()
        self.next_index = 0
        self.table.setRowCount(0)
        self.rows.clear()

    def set_delay(self, ms: int):
        """Update delay between frames."""
        self.delay_ms = max(1, int(ms))
        self.timer.setInterval(self.delay_ms)

    def is_playing(self) -> bool:
        return self.timer.isActive()

    # -------- Internal: playback tick --------
    def _on_tick(self):
        if self.next_index >= len(self.frames):
            self.timer.stop()
            return

        frame = self.frames[self.next_index]
        self._upsert(frame)
        self.next_index += 1

    # -------- Insert new row or update existing --------
    def _upsert(self, frame: CANFrame):
        key = self.get_key(frame)
        state = self.rows.get(key)

        if state is None:
            # Insert new row with CNT = frame.cnt (starts at 1)
            r = self.table.rowCount()
            self.table.insertRow(r)

            self._set_item(r, 0, str(frame.time))
            self._set_item(r, 1, f"0x{frame.id:X}", center=True)
            self._set_item(r, 2, frame.ext, center=True)
            self._set_item(r, 3, frame.dir, center=True)
            self._set_item(r, 4, str(frame.bus), center=True)
            self._set_item(r, 5, str(frame.cnt), center=True)   # CNT
            self._set_item(r, 6, str(frame.len), center=True)   # LEN

            for i in range(8):
                val = f"{frame.data[i]:02X}" if i < frame.len else ""
                self._set_item(r, 7 + i, val, center=True)

            self.rows[key] = (r, frame.cnt)
            self.table.resizeColumnsToContents()

        else:
            # Update existing row: increment CNT and refresh values
            r, cnt = state
            cnt += 1
            self.rows[key] = (r, cnt)

            # For display, we set latest values into the row
            self.table.item(r, 0).setText(str(frame.time))
            self.table.item(r, 1).setText(f"0x{frame.id:X}")
            self.table.item(r, 2).setText(frame.ext)
            self.table.item(r, 3).setText(frame.dir)
            self.table.item(r, 4).setText(str(frame.bus))
            self.table.item(r, 5).setText(str(cnt))        # CNT
            self.table.item(r, 6).setText(str(frame.len))  # LEN

            for i in range(8):
                if i < frame.len:
                    self.table.item(r, 7 + i).setText(f"{frame.data[i]:02X}")
                else:
                    self.table.item(r, 7 + i).setText("")

    # Helper to create table items
    def _set_item(self, row: int, col: int, text: str, center: bool = False):
        item = QTableWidgetItem(text)
        if center:
            item.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(row, col, item)


class StepGuide(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.steps = [
            "Step 1: Let the car be untoched in idle, then click confirm.",
            "Step 2: Wait 1 minute, then click confirm.",
            "Step 3: Initiate the action you want to identify, then click confirm.",
            "Step 4: Undo the action, then click confirm.",
            "Step 5: Done.",
        ]

        self.current = 0

        layout = QVBoxLayout(self)

        self.body = QLabel(self.steps[self.current])
        self.body.setWordWrap(True)
        layout.addWidget(self.body)

        self.btn_next = QPushButton("Next")
        self.btn_next.clicked.connect(self.on_next)
        layout.addWidget(self.btn_next)

    def on_next(self):
        self.current = (self.current + 1) % len(self.steps)
        self.body.setText(self.steps[self.current])


class InspectorPanel(QWidget):
    def __init__(self, data_tab: DataTab, parent=None):
        super().__init__(parent)
        
        self.data_tab = data_tab

        root = QVBoxLayout(self)

        delay_row = QHBoxLayout()
        delay_label = QLabel("Playback speed (ms):")
        self.delay_spin = QSpinBox()
        self.delay_spin.setRange(1, 1000)
        self.delay_spin.setValue(self.data_tab.delay_ms)
        self.delay_spin.valueChanged.connect(self.on_delay_changed)
        delay_row.addWidget(delay_label)
        delay_row.addWidget(self.delay_spin)
        root.addLayout(delay_row)

        btn_row = QHBoxLayout()

        self.btn_play_stop = QPushButton("Play")
        self.btn_play_stop.clicked.connect(self.on_play_stop)
        btn_row.addWidget(self.btn_play_stop)

        self.btn_restart = QPushButton("Restart")
        self.btn_restart.clicked.connect(self.on_restart)
        btn_row.addWidget(self.btn_restart)

        root.addLayout(btn_row)

        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setFrameShadow(QFrame.Sunken)
        root.addWidget(divider)

        self.step_guide = StepGuide()
        root.addWidget(self.step_guide)

        root.addStretch()
        self._sync_play_stop_label()

    def on_delay_changed(self, ms: int):
        self.data_tab.set_delay(ms)

    def on_play_stop(self):
        if self.data_tab.is_playing():
            self.data_tab.stop()
        else:
            self.data_tab.play()

        self._sync_play_stop_label()

    def on_restart(self):
        self.data_tab.restart()
        self._sync_play_stop_label()
        self.step_guide.on_reset()

    def _sync_play_stop_label(self):
        self.btn_play_stop.setText("Stop" if self.data_tab.is_playing() else "Play")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("CAN Scrape V5")
        self.resize(1200, 600)

        self.data_tab = DataTab()
        self.inspector_panel = InspectorPanel(self.data_tab)

        splitter = QSplitter()
        splitter.addWidget(self.data_tab)
        splitter.addWidget(self.inspector_panel)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)

        self.setCentralWidget(splitter)

        # Load CSV and auto-start playback
        try:
            frames = read_data_file(DATA_FILE)

            if not frames:
                QMessageBox.warning(self, "No Data", f"No frames found in '{DATA_FILE}'.")
            
            self.data_tab.load_frames(frames)
            self.data_tab.play()
        except FileNotFoundError:
            QMessageBox.critical(self, "File Not Found", f"Could not find '{DATA_FILE}'.")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()