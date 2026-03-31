from PySide6.QtWidgets import (
    QFileDialog, QHBoxLayout, QLabel, QPushButton, QButtonGroup, QVBoxLayout, QWidget
)

from can_writer import raw_csv_export, training_csv_export, troys_csv_export, troys_json_export
from settings import DetectionMode, InputMode, Settings

class InspectorWidget(QWidget):
    def __init__(self, settings_model: Settings):
        super().__init__()
        
        self.settings = settings_model
        self.vlayout = QVBoxLayout()

        self.csv_label = QLabel("No CSV loaded...", wordWrap=True)

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
        header = QLabel("<b>Config</b>")
        self.vlayout.addWidget(header)

        hlayout = QHBoxLayout()

        button = QPushButton("Load Csv")
        button.clicked.connect(self.on_load_csv_clicked)

        hlayout.addWidget(button)
        hlayout.addWidget(self.csv_label)
        self.vlayout.addLayout(hlayout)

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

    def detection_mode_gui(self):
        header = QLabel("<b>Detection mode</b>")
        self.vlayout.addWidget(header)

        names = ["Off", "Noise", "Event"]
        group = QButtonGroup(self)
        hlayout = QHBoxLayout()

        for i, name in enumerate(names):
            b = QPushButton(name)
            b.setCheckable(True)
            group.addButton(b, id=i)
            hlayout.addWidget(b)

        group.idClicked.connect(self.on_detection_mode_changed)
        group.buttons()[0].setChecked(True)
        self.vlayout.addLayout(hlayout)

    def event_selection_gui(self):
        header = QLabel("<b>Event selection</b>")
        self.vlayout.addWidget(header)

        layout = QVBoxLayout()
        group = QButtonGroup(self)

        for event in self.settings.event_intervals.keys():
            button = QPushButton(event)
            button.setCheckable(True)
            group.addButton(button)
            layout.addWidget(button)

        group.buttonClicked.connect(self.on_event_clicked)
        group.buttons()[0].click()
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

        hlayout = QHBoxLayout()
        b0 = QPushButton("Raw export")
        b1 = QPushButton("Troy's export")
        b2 = QPushButton("Training export")
        b0.clicked.connect(self.on_raw_csv_export_clicked)
        b1.clicked.connect(self.on_troys_csv_export_clicked)
        b2.clicked.connect(self.on_training_csv_export_clicked)
        hlayout.addWidget(b0)
        hlayout.addWidget(b1)
        hlayout.addWidget(b2)
        self.vlayout.addLayout(hlayout)

    def on_load_csv_clicked(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load CSV", "", "CSV Files (*.csv)")
        if path:
            self.settings.csv_filepath = path
            self.csv_label.setText(f"{self.settings.csv_filepath}")

    def on_input_mode_changed(self, id: int):
        if id == 0:
            self.settings.setInputMode(InputMode.Off)
        elif id == 1:
            self.settings.setInputMode(InputMode.PeakCan)
        elif id == 2:
            self.settings.setInputMode(InputMode.SerialPort)
        elif id == 3:
            self.settings.setInputMode(InputMode.CsvReplay)
    
        if self.settings.reader:
            self.settings.reader.msg_signal.connect(self.update_gui)
            self.settings.reader.start()

    def on_detection_mode_changed(self, id: int):
        if id == 2 and self.settings.detectionMode() != DetectionMode.Event:
            self.settings.event_intervals[self.settings.selected_event].start_index = self.settings.frame_count
            self.settings.reset_event_bits()
        elif id != 2 and self.settings.detectionMode() == DetectionMode.Event:
            self.settings.event_intervals[self.settings.selected_event].end_index = self.settings.frame_count
            # Todo: Inspector should not handle this, I think.
            for can_id, frame in self.settings.frames.items():
                for byte_bits in frame.event_bits:
                    if any(byte_bits):
                        self.settings.event_intervals[self.settings.selected_event].interesting_ids.append(can_id)
                        break

        if id == 0:
            self.settings.setDetectionMode(DetectionMode.Off)
        elif id == 1:
            self.settings.setDetectionMode(DetectionMode.Noise)
        elif id == 2:
            self.settings.setDetectionMode(DetectionMode.Event)

    def on_event_clicked(self, button: QPushButton):
        self.settings.selected_event = button.text()
        self.settings.onEventClicked.emit(button.text())

    def on_raw_csv_export_clicked(self):
        raw_csv_export(self.settings.all_frames, "output/raw-export.csv")

    def on_troys_csv_export_clicked(self):
        troys_csv_export(self.settings.all_frames, "output/troys-export.csv")
        troys_json_export(self.settings.event_intervals, "output/troys-export.json")

    def on_training_csv_export_clicked(self):
        training_csv_export(self.settings.all_frames, "output/training-export.csv")

    def update_gui(self):
        self.time_label.setText(f"Time: {(self.settings.current_timestamp - self.settings.initial_timestamp):.3f}")
        self.frame_count_label.setText(f"Frame count: {self.settings.frame_count}")