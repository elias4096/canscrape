from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QComboBox, QFileDialog, QFrame, QHBoxLayout,
    QLabel, QPushButton, QRadioButton, QSizePolicy, QVBoxLayout, QWidget
)

import serial.tools.list_ports
from can_writer import baseline_csv_export
from settings import Settings


class BaselineSelectorWidget(QWidget):
    baseline_done = Signal(str)
    recording_start = Signal(str, str)

    def __init__(self, settings: Settings):
        super().__init__()
        self.setWindowTitle("Baseline Setup")
        self.setMinimumWidth(480)
        self.setMinimumHeight(320)

        self.settings = settings

        self.selected_file: str | None = None
        self.recording_done = False
        self.result_path: str | None = None
        self._csv_replay_path: str = ""

        self._build_ui()
        self._update_state()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(20)
        root.setContentsMargins(32, 28, 32, 24)

        title = QLabel("Baseline Configuration")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        root.addWidget(title)

        subtitle = QLabel("Choose how you want to provide the baseline data.")
        subtitle.setStyleSheet("color: #888;")
        root.addWidget(subtitle)

        root.addWidget(self._divider())

        self.radio_existing = QRadioButton("Use a prerecorded baseline file")
        self.radio_existing.setFont(QFont("Segoe UI", 10))
        self.radio_existing.toggled.connect(self._on_option_changed)
        root.addWidget(self.radio_existing)

        self.existing_row = QWidget()
        h1 = QHBoxLayout(self.existing_row)
        h1.setContentsMargins(24, 0, 0, 0)
        h1.setSpacing(10)

        self.file_label = QLabel("No file selected")
        self.file_label.setStyleSheet("color: #aaa; font-style: italic;")
        self.file_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        self.browse_btn = QPushButton("Browse…")
        self.browse_btn.setFixedWidth(90)
        self.browse_btn.clicked.connect(self._browse_file)

        h1.addWidget(self.file_label)
        h1.addWidget(self.browse_btn)
        root.addWidget(self.existing_row)

        self.radio_record = QRadioButton("Record a new baseline file")
        self.radio_record.setFont(QFont("Segoe UI", 10))
        self.radio_record.toggled.connect(self._on_option_changed)
        root.addWidget(self.radio_record)

        self.record_row = QWidget()
        v2 = QVBoxLayout(self.record_row)
        v2.setContentsMargins(24, 0, 0, 0)
        v2.setSpacing(6)

        input_mode_row = QHBoxLayout()
        self.input_mode_group = QButtonGroup(self)
        for i, name in enumerate(["PeakCAN", "Serial Port", "CSV Replay"]):
            b = QPushButton(name)
            b.setCheckable(True)
            self.input_mode_group.addButton(b, id=i)
            input_mode_row.addWidget(b)
        self.input_mode_group.buttons()[0].setChecked(True)
        self.input_mode_group.idClicked.connect(self._on_input_mode_clicked)
        v2.addLayout(input_mode_row)

        self.port_combo = QComboBox()
        self.port_combo.hide()
        self._refresh_ports()

        port_row = QHBoxLayout()
        port_row.addWidget(self.port_combo)
        refresh_btn = QPushButton("↻")
        refresh_btn.setFixedWidth(30)
        refresh_btn.clicked.connect(self._refresh_ports)
        port_row.addWidget(refresh_btn)
        v2.addLayout(port_row)

        record_ctrl_row = QHBoxLayout()
        self.record_btn = QPushButton("⏺  Start Recording")
        self.record_btn.setFixedWidth(160)
        self.record_btn.setCheckable(True)
        self.record_btn.clicked.connect(self._on_record_clicked)

        self.record_status = QLabel("")
        self.record_status.setStyleSheet("color: #aaa; font-style: italic;")

        record_ctrl_row.addWidget(self.record_btn)
        record_ctrl_row.addWidget(self.record_status)
        v2.addLayout(record_ctrl_row)

        root.addWidget(self.record_row)

        self.group = QButtonGroup(self)
        self.group.addButton(self.radio_existing)
        self.group.addButton(self.radio_record)

        root.addStretch()
        root.addWidget(self._divider())

        bottom = QHBoxLayout()
        bottom.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setFixedWidth(90)
        self.cancel_btn.clicked.connect(QApplication.quit)

        self.next_btn = QPushButton("Next →")
        self.next_btn.setFixedWidth(100)
        self.next_btn.setDefault(True)
        self.next_btn.clicked.connect(self._on_next)

        bottom.addWidget(self.cancel_btn)
        bottom.addWidget(self.next_btn)
        root.addLayout(bottom)

    def _divider(self):
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #333;")
        return line

    def _on_option_changed(self):
        self.selected_file = None
        self.recording_done = False
        self.record_btn.setChecked(False)
        self.record_btn.setEnabled(True)
        self.record_btn.setText("⏺  Start Recording")
        self.record_status.setText("")
        self.file_label.setText("No file selected")
        self.file_label.setStyleSheet("color: #aaa; font-style: italic;")
        self._update_state()

    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select baseline file", "", "CSV files (*.csv)"
        )
        if path:
            self.selected_file = path
            self.file_label.setText(path.split("/")[-1])
            self.file_label.setStyleSheet("color: #ccc; font-style: normal;")
        self._update_state()

    def _refresh_ports(self):
        self.port_combo.clear()
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.port_combo.addItems(ports if ports else ["No ports found"])

    def _on_input_mode_clicked(self, id: int):
        self.port_combo.setVisible(id == 1)
        if id == 1:
            self._refresh_ports()
        elif id == 2:
            path, _ = QFileDialog.getOpenFileName(
                self, "Select CAN CSV file", "", "CSV files (*.csv)"
            )
            if path:
                self._csv_replay_path = path
            else:
                self._csv_replay_path = ""
                self.input_mode_group.buttons()[0].setChecked(True)

    def _on_record_clicked(self, checked: bool):
        if checked:
            mode_id = self.input_mode_group.checkedId()
            modes = ["PeakCAN", "SerialPort", "CsvReplay"]
            if mode_id == 1:
                port = self.port_combo.currentText()
                if port != "No ports found":
                    self.settings.serial_port = port
            self.recording_start.emit(modes[mode_id], self._csv_replay_path)
            self.record_btn.setText("⏹  Stop Recording")
            self.record_status.setText("Recording…")
            self.record_status.setStyleSheet("color: #e06c6c;")
            self.recording_done = False
        else:
            self.recording_start.emit("Off", "")
            path = baseline_csv_export(self.settings.all_frames, "src/output/baseline-export.csv")
            print(f"Exported to: {path}")
            self.result_path = path
            self.recording_done = True
            self.record_btn.setText("✔  Recording saved")
            self.record_btn.setEnabled(False)
            self.record_status.setText(f"Saved ({len(self.settings.all_frames)} frames)")
            self.record_status.setStyleSheet("color: #6cc96c;")
        self._update_state()

    def _update_state(self):
        self.existing_row.setEnabled(self.radio_existing.isChecked())
        self.record_row.setEnabled(self.radio_record.isChecked())

        if self.radio_existing.isChecked() and self.selected_file:
            self.next_btn.setEnabled(True)
        elif self.radio_record.isChecked() and self.recording_done:
            self.next_btn.setEnabled(True)
        else:
            self.next_btn.setEnabled(False)

    def _on_next(self):
        if self.radio_existing.isChecked():
            self.result_path = self.selected_file
            self.settings.baseline_is_recording = False
        else:
            self.settings.baseline_is_recording = True
        self.baseline_done.emit(self.result_path)