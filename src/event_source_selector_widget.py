import os
import shutil

from PySide6.QtCore import Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QFileDialog, QFrame, QHBoxLayout,
    QLabel, QPushButton, QRadioButton, QSizePolicy, QVBoxLayout, QWidget
)

from settings import Settings


class EventSourceSelectorWidget(QWidget):
    record_chosen   = Signal()
    recording_start = Signal(str, str)
    analysis_done   = Signal()

    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings

        self._raw_csv_path:    str | None = None
        self._event_json_path: str | None = None

        self._build_ui()
        self._update_state()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(20)
        root.setContentsMargins(32, 28, 32, 24)

        title = QLabel("Event Source")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        root.addWidget(title)

        subtitle = QLabel("How do you want to provide the event data?")
        subtitle.setStyleSheet("color: #888;")
        root.addWidget(subtitle)

        root.addWidget(self._divider())

        self.radio_record = QRadioButton("Record new events")
        self.radio_record.setFont(QFont("Segoe UI", 10))
        self.radio_record.toggled.connect(self._update_state)
        root.addWidget(self.radio_record)

        self.radio_existing = QRadioButton("Use existing CSV and JSON files")
        self.radio_existing.setFont(QFont("Segoe UI", 10))
        self.radio_existing.toggled.connect(self._update_state)
        root.addWidget(self.radio_existing)

        self.existing_row = QWidget()
        v = QVBoxLayout(self.existing_row)
        v.setContentsMargins(24, 0, 0, 0)
        v.setSpacing(8)

        csv_row = QHBoxLayout()
        self.csv_label = QLabel("No CSV file selected")
        self.csv_label.setStyleSheet("color: #aaa; font-style: italic;")
        self.csv_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        csv_browse = QPushButton("Browse…")
        csv_browse.setFixedWidth(90)
        csv_browse.clicked.connect(self._browse_csv)
        csv_row.addWidget(self.csv_label)
        csv_row.addWidget(csv_browse)
        v.addLayout(csv_row)

        json_row = QHBoxLayout()
        self.json_label = QLabel("No JSON file selected")
        self.json_label.setStyleSheet("color: #aaa; font-style: italic;")
        self.json_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        json_browse = QPushButton("Browse…")
        json_browse.setFixedWidth(90)
        json_browse.clicked.connect(self._browse_json)
        json_row.addWidget(self.json_label)
        json_row.addWidget(json_browse)
        v.addLayout(json_row)

        root.addWidget(self.existing_row)

        self._radio_group = QButtonGroup(self)
        self._radio_group.addButton(self.radio_record)
        self._radio_group.addButton(self.radio_existing)

        root.addStretch()
        root.addWidget(self._divider())

        bottom = QHBoxLayout()
        bottom.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedWidth(90)
        cancel_btn.clicked.connect(QApplication.quit)

        self.next_btn = QPushButton("Next →")
        self.next_btn.setFixedWidth(100)
        self.next_btn.setDefault(True)
        self.next_btn.clicked.connect(self._on_next)

        bottom.addWidget(cancel_btn)
        bottom.addWidget(self.next_btn)
        root.addLayout(bottom)

    def _divider(self):
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #333;")
        return line

    def _browse_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select raw event CSV", "", "CSV files (*.csv)")
        if path:
            self._raw_csv_path = path
            self.csv_label.setText(path.split("/")[-1])
            self.csv_label.setStyleSheet("color: #ccc; font-style: normal;")
        self._update_state()

    def _browse_json(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select event indexes JSON", "", "JSON files (*.json)")
        if path:
            self._event_json_path = path
            self.json_label.setText(path.split("/")[-1])
            self.json_label.setStyleSheet("color: #ccc; font-style: normal;")
        self._update_state()

    def _update_state(self):
        is_existing = self.radio_existing.isChecked()
        self.existing_row.setEnabled(is_existing)

        if self.radio_record.isChecked():
            self.next_btn.setEnabled(True)
        elif is_existing and self._raw_csv_path and self._event_json_path:
            self.next_btn.setEnabled(True)
        else:
            self.next_btn.setEnabled(False)

    def _on_next(self):
        if self.radio_record.isChecked():
            self.recording_start.emit("Clear", "")
            self.record_chosen.emit()
        else:
            assert self._raw_csv_path is not None
            assert self._event_json_path is not None

            self.settings.last_export_raw  = self._raw_csv_path
            self.settings.last_export_json = self._event_json_path

            dest = os.path.join("src/output", os.path.basename(self.settings.baseline_path))
            shutil.copy2(self.settings.baseline_path, dest)
            self.settings.last_export_baseline = dest

            self.settings.loadCsvSnapshot.emit(self._raw_csv_path)
            self.analysis_done.emit()