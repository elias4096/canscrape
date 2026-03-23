from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDockWidget, QMainWindow, QTabWidget, QVBoxLayout, QWidget

from data_widget import DataWidget
from inspector_widget import InspectorWidget
from result_widget import ResultWidget
from settings import Settings

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Can Scrape")

        settings_model = Settings()

        data_tab = DataWidget(settings_model)
        result_tab = ResultWidget(settings_model)

        tabs = QTabWidget()
        tabs.addTab(data_tab, "Data")
        tabs.addTab(result_tab, "Result")

        inspector_widget = InspectorWidget(settings_model)
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