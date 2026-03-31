from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDockWidget, QMainWindow, QTabWidget, QVBoxLayout, QWidget

from autoencoder_detector_widget import AutoencoderDetectorWidget
from data_widget import DataWidget
from inspector_widget import InspectorWidget
from result_widget import ResultWidget
from settings import Settings

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Can Scrape")

        settings = Settings()

        data_tab = DataWidget(settings)
        result_tab = ResultWidget(settings)
        autoencoder_detector_tab = AutoencoderDetectorWidget(settings)

        tabs = QTabWidget()
        tabs.addTab(data_tab, "Data")
        tabs.addTab(result_tab, "Result")
        tabs.addTab(autoencoder_detector_tab, "Autoencoder detector")

        inspector_widget = InspectorWidget(settings)
        inspector_dock = QDockWidget("Inspector", self)
        inspector_dock.setWidget(inspector_widget)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, inspector_dock)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addWidget(tabs)
        self.setCentralWidget(central)

if __name__ == "__main__":
    app = QApplication()
    window = MainWindow()
    window.resize(1280, 720)
    window.show()
    app.exec()