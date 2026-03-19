from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QListWidget, QPushButton, QRadioButton, QButtonGroup, QScrollArea, QVBoxLayout, QWidget, QFileDialog
)

from can_writer import export_events_to_json, export_frames_to_csv
from dot_widget import DotWidget
from typing import TYPE_CHECKING, Dict

from models import CanFunction

if TYPE_CHECKING:
    from main import MainWindow


class InspectorWidget(QWidget):
    def __init__(self, main_window: MainWindow):
        super().__init__()
        self.main_window = main_window

        layout = QVBoxLayout()

        self.elapsed_label = QLabel("Elapsed time:")
        layout.addWidget(self.elapsed_label)

        self.pcan_radio = QRadioButton("PeakCAN")
        self.pcan_radio.setChecked(True)
        self.serial_radio = QRadioButton("Serial port")
        self.csv_radio = QRadioButton("CSV replay")

        self.group = QButtonGroup()
        self.group.addButton(self.pcan_radio)
        self.group.addButton(self.serial_radio)
        self.group.addButton(self.csv_radio)

        layout.addWidget(self.pcan_radio)
        layout.addWidget(self.serial_radio)
        layout.addWidget(self.csv_radio)

        self.load_csv_button = QPushButton("Load CSV")
        self.load_csv_button.clicked.connect(self.select_csv_file)
        layout.addWidget(self.load_csv_button)

        self.start_button = QPushButton("Start")
        self.start_button.clicked.connect(lambda: main_window.start_reader())

        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(main_window.stop_reader)

        playback_layout = QHBoxLayout()
        playback_layout.addWidget(self.start_button)
        playback_layout.addWidget(self.stop_button)
        layout.addLayout(playback_layout)

        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(main_window.clear)
        layout.addWidget(self.clear_button)

        self.noise1_button = QPushButton("Start noise detection")
        self.noise1_button.clicked.connect(self.toggle_noise1)
        layout.addWidget(self.noise1_button)

        self.noise2_button = QPushButton("Start action detection")
        self.noise2_button.clicked.connect(self.toggle_noise2)
        layout.addWidget(self.noise2_button)

        self.export_button = QPushButton("Export")
        self.export_button.clicked.connect(self.export)
        layout.addWidget(self.export_button)

        self.selected_function_label = QLabel("Selected function: None")
        layout.addWidget(self.selected_function_label)

        self.status_dots: Dict[str, CanFunction] = {}

        self.selected_function: str = ""

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        actions = [
            "Hazard lights",
            "Footbrake",
            "Park brake",
            "Wipers",
            "Drivers door",
            "Passenger door",
            "Rear left door",
            "Rear right door",
            "Drivers seat belt",
            "Front Passenger seat belt",
        ]

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)

        container = QWidget()
        container_layout = QVBoxLayout(container)

        for label in actions:
            row = QHBoxLayout()

            dot = DotWidget()
            self.status_dots[label] = CanFunction(dot, 0.0, 0.0, [])
            row.addWidget(dot)

            btn = QPushButton(label)
            btn.clicked.connect(lambda _, text=label: self.handle_action_click(text))
            row.addWidget(btn)

            container_layout.addLayout(row)

        container_layout.addStretch()

        scroll_area.setWidget(container)
        layout.addWidget(scroll_area)

        layout.addStretch()
        self.setLayout(layout)

    def select_csv_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load CSV", "", "CSV Files (*.csv)")
        if path:
            self.main_window.csv_path = path
            self.csv_radio.setChecked(True)

    def toggle_noise1(self):
        self.main_window.running_noise1 = not self.main_window.running_noise1
        self.noise1_button.setText("Stop noise detection" if self.main_window.running_noise1 else "Start noise detection")

    def toggle_noise2(self):
        self.main_window.running_noise2 = not self.main_window.running_noise2
        if self.main_window.running_noise2:
            self.noise2_button.setText("Stop action detection")
            if self.selected_function:
                self.status_dots[self.selected_function].end_time = self.main_window.current_timestamp
        else:
            self.noise2_button.setText("Start action detection")
            if self.selected_function:
                self.status_dots[self.selected_function].start_time = self.main_window.current_timestamp

    def handle_action_click(self, action_name: str) -> None:
        self.selected_function = action_name
        self.selected_function_label.setText(f"Selected function: {self.selected_function}")

        self.refresh_list_widget()

    def export(self) -> None:
        export_frames_to_csv(self.main_window.can_frames)
        export_events_to_json(self.status_dots)

    def refresh_list_widget(self):
        self.list_widget.clear()

        if self.selected_function not in self.status_dots:
            return

        for can_id in self.status_dots[self.selected_function].can_ids:
            self.list_widget.addItem(f"{can_id:03X}")
            self.status_dots[self.selected_function].dot.set_color("yellow")
