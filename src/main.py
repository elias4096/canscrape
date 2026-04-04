from PySide6.QtCore import Qt, QProcess
from PySide6.QtWidgets import QApplication, QDockWidget, QMainWindow, QTabWidget, QVBoxLayout, QWidget

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'event-bits'))

from analysis import get_noise_bits
from analysis_result_widget import AnalysisResultWidget
from autoencoder_detector_widget import AutoencoderDetectorWidget
from baseline_selector_widget import BaselineSelectorWidget
from data_widget import DataWidget
from event_source_selector_widget import EventSourceSelectorWidget
from inspector_widget import InspectorWidget
from result_widget import ResultWidget
from settings import InputMode, Settings


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Can Scrape")

        self.settings = Settings()
        self._process: QProcess | None = None

        data_tab = DataWidget(self.settings)
        result_tab = ResultWidget(self.settings)
        autoencoder_detector_tab = AutoencoderDetectorWidget(self.settings)
        self.analysis_result_tab = AnalysisResultWidget()

        self.tabs = QTabWidget()
        self.tabs.addTab(data_tab, "Data")
        self.tabs.addTab(result_tab, "Result")
        self.tabs.addTab(autoencoder_detector_tab, "Autoencoder detector")
        self.tabs.addTab(self.analysis_result_tab, "Bit Analysis")

        self.dock = QDockWidget("Baseline Setup", self)
        self.dock.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        self.selector = BaselineSelectorWidget(self.settings)
        self.selector.baseline_done.connect(self._on_baseline_done)
        self.selector.recording_start.connect(self._on_recording_start)
        self.dock.setWidget(self.selector)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addWidget(self.tabs)
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

        event_selector = EventSourceSelectorWidget(self.settings)
        event_selector.record_chosen.connect(self._on_record_chosen)
        event_selector.recording_start.connect(self._on_recording_start)
        event_selector.analysis_done.connect(self._on_analysis_done)
        self.dock.setWindowTitle("Event Source")
        self.dock.setWidget(event_selector)

    def _on_record_chosen(self):
        inspector_widget = InspectorWidget(self.settings)
        inspector_widget.run_analysis.connect(self._on_analysis_done)
        self.dock.setWindowTitle("Inspector")
        self.dock.setWidget(inspector_widget)

    def _on_analysis_done(self):
        self.analysis_result_tab.show_running()
        self.tabs.setCurrentWidget(self.analysis_result_tab)
        self.dock.hide()

        self._process = QProcess(self)
        self._process.setProgram("python")
        self._process.setArguments([
            "event-bits/main.py",
            self.settings.last_export_baseline,
            self.settings.last_export_raw,
            self.settings.last_export_json,
        ])
        self._process.finished.connect(self._on_process_finished)
        self._process.errorOccurred.connect(
            lambda err: self.analysis_result_tab.show_error(str(err))
        )
        self._process.start()

    def _on_process_finished(self, exit_code: int, exit_status):
        assert self._process is not None
        stdout = self._process.readAllStandardOutput().toStdString()
        stderr = self._process.readAllStandardError().toStdString()

        if exit_code != 0:
            self.analysis_result_tab.show_error(stderr.strip() or f"exit code {exit_code}")
        else:
            self.analysis_result_tab.load_output(stdout)


if __name__ == "__main__":
    app = QApplication()

    window = MainWindow()
    window.resize(1280, 720)
    window.show()
    app.exec()