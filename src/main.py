from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDockWidget, QMainWindow, QTabWidget, QVBoxLayout, QWidget

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'event-bits'))

from analysis import get_noise_bits
from autoencoder_detector_widget import AutoencoderDetectorWidget
from baseline_selector_widget import BaselineSelectorWidget
from data_widget import DataWidget
from inspector_widget import InspectorWidget
from result_widget import ResultWidget
from settings import InputMode, Settings


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Can Scrape")

        self.settings = Settings()

        data_tab = DataWidget(self.settings)
        result_tab = ResultWidget(self.settings)
        autoencoder_detector_tab = AutoencoderDetectorWidget(self.settings)

        tabs = QTabWidget()
        tabs.addTab(data_tab, "Data")
        tabs.addTab(result_tab, "Result")
        tabs.addTab(autoencoder_detector_tab, "Autoencoder detector")

        self.dock = QDockWidget("Baseline Setup", self)
        self.dock.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        self.selector = BaselineSelectorWidget(self.settings)
        self.selector.baseline_done.connect(self._on_baseline_done)
        self.selector.recording_start.connect(self._on_recording_start)
        self.dock.setWidget(self.selector)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addWidget(tabs)
        self.setCentralWidget(central)

    def _on_recording_start(self, mode: str, csv_path: str):
        if mode == "PeakCan":
            self.settings.setInputMode(InputMode.PeakCan)
        elif mode == "SerialPort":
            self.settings.setInputMode(InputMode.SerialPort)
        elif mode == "CsvReplay":
            self.settings.csv_filepath = csv_path
            self.settings.setInputMode(InputMode.CsvReplay)
        elif mode == "Off":
            self.settings.setInputMode(InputMode.Off)
        elif mode == "Clear":
            self.settings.setInputMode(InputMode.Off)
            self.settings.clearData.emit()

    def _on_baseline_done(self, result_path: str):
        self.settings.baseline_path = result_path
        self.settings.baseline_noise_bits = get_noise_bits(result_path)
        inspector_widget = InspectorWidget(self.settings)
        self.dock.setWindowTitle("Inspector")
        self.dock.setWidget(inspector_widget)


if __name__ == "__main__":
    app = QApplication()

    window = MainWindow()
    window.resize(1280, 720)
    window.show()
    app.exec()