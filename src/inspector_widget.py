from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog, QHBoxLayout, QInputDialog, QLabel, QPushButton, QButtonGroup, QVBoxLayout, QWidget
)

from os.path import basename
import serial.tools.list_ports

from can_writer import raw_csv_export, event_indexes_json_export, baseline_export_copy
from settings import DetectionMode, InputMode, Settings


class InspectorWidget(QWidget):
    run_analysis = Signal()
    def __init__(self, settings_model: Settings):
        super().__init__()
        
        self.settings = settings_model
        self.vlayout = QVBoxLayout()

        self.time_label = QLabel("Time: ---")
        self.frame_count_label = QLabel("Frame count: ---")
        self.vlayout.addWidget(self.time_label)
        self.vlayout.addWidget(self.frame_count_label)

        self.config_gui()
        self.input_mode_gui()
        self.detection_mode_gui()
        self.event_selection_gui()
        self.isolation_forest_gui()
        self.export_gui()

        self.vlayout.addStretch()
        self.setLayout(self.vlayout)

    def config_gui(self):
        header = QLabel("<b>Baseline</b>")
        self.vlayout.addWidget(header)

        filename = basename(self.settings.baseline_path) if self.settings.baseline_path else "unknown"
        label = "Saved as" if self.settings.baseline_is_recording else "Loaded from"
        status_label = QLabel(f"✔ Baseline configured\n{label}: {filename}")
        status_label.setStyleSheet("""
            QLabel {
                color: #15803d;
                background-color: #e6f9ec;
                border: 1px solid #b6e2c6;
                border-radius: 8px;
                padding: 6px 10px;
                font-weight: 500;
            }
        """)
        self.vlayout.addWidget(status_label)

    def input_mode_gui(self):
        header = QLabel("<b>Input mode</b>")
        self.vlayout.addWidget(header)

        names = ["Off", "PeakCan", "Serial Port", "Csv Replay"]
        group = QButtonGroup(self)
        hlayout = QHBoxLayout()

        for i, name in enumerate(names):
            b = QPushButton(name)
            b.setCheckable(True)
            group.addButton(b, id=i)
            hlayout.addWidget(b)

        group.buttons()[0].setChecked(True)
        group.idClicked.connect(self.on_input_mode_changed)
        self.vlayout.addLayout(hlayout)

        self.csv_label = QLabel("", wordWrap=True)
        self.csv_label.setStyleSheet("color: #ccc; font-style: normal;")
        self.csv_label.hide()
        self.vlayout.addWidget(self.csv_label)

    def detection_mode_gui(self):
        header = QLabel("<b>Detection mode</b>")
        self.vlayout.addWidget(header)

        names = ["On", "Off"]
        group = QButtonGroup(self)
        hlayout = QHBoxLayout()

        for i, name in enumerate(names):
            b = QPushButton(name)
            b.setCheckable(True)
            group.addButton(b, id=i)
            hlayout.addWidget(b)

        group.button(1).setChecked(True)
        group.idClicked.connect(self.on_detection_mode_changed)
        self.vlayout.addLayout(hlayout)

    def event_selection_gui(self):
        header = QLabel("<b>Event selection</b>")
        self.vlayout.addWidget(header)

        layout = QVBoxLayout()
        self.event_group = QButtonGroup(self)

        for event in self.settings.event_intervals.keys():
            button = QPushButton(event)
            button.setCheckable(True)
            self.event_group.addButton(button)
            layout.addWidget(button)

        self.event_group.buttonClicked.connect(self.on_event_clicked)
        self.vlayout.addLayout(layout)

    def isolation_forest_gui(self):
        header = QLabel("<b>Isolation forest</b>")
        self.vlayout.addWidget(header)

        b2 = QPushButton("Run")
        b2.clicked.connect(self.settings.onIsolationForestClicked.emit)
        self.vlayout.addWidget(b2)

    def export_gui(self):
        header = QLabel("<b>Export</b>")
        self.vlayout.addWidget(header)

        self.export_btn = QPushButton("Export")
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self.on_export_clicked)
        self.vlayout.addWidget(self.export_btn)

        self.run_analysis_btn = QPushButton("Run analysis")
        self.run_analysis_btn.setEnabled(False)
        self.run_analysis_btn.clicked.connect(self.on_run_analysis_clicked)
        self.vlayout.addWidget(self.run_analysis_btn)

    def on_input_mode_changed(self, id: int):
        if id == 0:
            self.settings.setInputMode(InputMode.Off)
            self.csv_label.hide()
            self.export_btn.setEnabled(True)
        elif id == 1:
            self.settings.setInputMode(InputMode.PeakCan)
            self.csv_label.hide()
            self.export_btn.setEnabled(False)
            self.run_analysis_btn.setEnabled(False)
        elif id == 2:
            ports = [p.device for p in serial.tools.list_ports.comports()]
            if not ports:
                ports = ["No ports found"]
            port, ok = QInputDialog.getItem(self, "Select Serial Port", "Port:", ports, 0, False)
            if ok and port != "No ports found":
                self.settings.serial_port = port
                self.csv_label.setText(f"▶ {port}")
                self.csv_label.setStyleSheet("color: #ccc; font-style: normal;")
                self.csv_label.show()
                self.settings.setInputMode(InputMode.SerialPort)
                self.export_btn.setEnabled(False)
                self.run_analysis_btn.setEnabled(False)
            else:
                return
        elif id == 3:
            path, _ = QFileDialog.getOpenFileName(self, "Select CAN CSV file", "", "CSV Files (*.csv)")
            if path:
                self.settings.csv_filepath = path
                self.csv_label.setText(f"▶ {path.split('/')[-1]}")
                self.csv_label.setStyleSheet("color: #ccc; font-style: normal;")
                self.csv_label.show()
                self.settings.setInputMode(InputMode.CsvReplay)
                self.export_btn.setEnabled(False)
                self.run_analysis_btn.setEnabled(False)
            else:
                return

        if self.settings.reader:
            self.settings.reader.msg_signal.connect(self.update_gui)
            self.settings.reader.start()

    def on_detection_mode_changed(self, id: int):
        if id == 0 and self.settings.detectionMode() != DetectionMode.Event:
            self.settings.event_intervals[self.settings.selected_event].start_index = self.settings.frame_count
            self.settings.reset_event_bits()
            self.settings.setDetectionMode(DetectionMode.Event)
        elif id == 1 and self.settings.detectionMode() == DetectionMode.Event:
            self.settings.event_intervals[self.settings.selected_event].end_index = self.settings.frame_count
            for can_id, frame in self.settings.frames.items():
                for byte_bits in frame.event_bits:
                    if any(byte_bits):
                        self.settings.event_intervals[self.settings.selected_event].interesting_ids.append(can_id)
                        break
            self.settings.setDetectionMode(DetectionMode.Off)
            checked = self.event_group.checkedButton()
            if checked:
                self.event_group.setExclusive(False)
                checked.setChecked(False)
                self.event_group.setExclusive(True)
            self.settings.selected_event = ""

    def on_event_clicked(self, button: QPushButton):
        self.settings.selected_event = button.text()
        self.settings.onEventClicked.emit(button.text())

    def on_export_clicked(self):
        path = raw_csv_export(self.settings.all_frames, "src/output/raw-export.csv")
        print(f"Exported to: {path}")
        self.settings.last_export_raw = path

        path = event_indexes_json_export(self.settings.event_intervals, "src/output/event_indexes.json")
        print(f"Exported to: {path}")
        self.settings.last_export_json = path

        if self.settings.baseline_path:
            path = baseline_export_copy(self.settings.baseline_path, "src/output")
            print(f"Exported to: {path}")
            self.settings.last_export_baseline = path

        self.run_analysis_btn.setEnabled(True)

    def on_run_analysis_clicked(self):
        self.run_analysis.emit()

    def update_gui(self):
        t = self.settings.current_timestamp
        minutes = int(t // 60)
        seconds = int(t % 60)
        milliseconds = int((t % 1) * 1000)
        self.time_label.setText(f"Time: {minutes}m {seconds}s {milliseconds}ms")
        self.frame_count_label.setText(f"Frame count: {self.settings.frame_count}")