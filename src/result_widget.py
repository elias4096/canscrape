from PySide6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget, QSplitter
)
from PySide6.QtCore import Qt

from isolation_forest import likelihood_from_frames
from settings import Settings


class ResultWidget(QWidget):
    def __init__(self, settings_model: Settings):
        super().__init__()

        self.settings = settings_model
        self.settings.detectionModeChanged.connect(self.on_detection_mode_changed)
        self.settings.onIsolationForestClicked.connect(self.on_isolation_forest_clicked)
        self.settings.onEventClicked.connect(self.on_event_clicked)

        vlayout = QVBoxLayout()
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.table_left = QTableWidget(0, 9)
        self.table_left.setHorizontalHeaderLabels([
            "ID","D1","D2","D3","D4","D5","D6","D7","D8"
        ])
        self.table_left.setAlternatingRowColors(True)
        self.table_left.resizeColumnsToContents()
        self.table_left.horizontalHeader().setStretchLastSection(True)
        self.table_left.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        self.table_right = QTableWidget(0, 1)
        self.table_right.setHorizontalHeaderLabels([
            "ID", "Count"
        ])
        self.table_right.setAlternatingRowColors(True)
        self.table_right.resizeColumnsToContents()
        self.table_right.horizontalHeader().setStretchLastSection(True)
        self.table_right.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        splitter.addWidget(self.table_left)
        splitter.addWidget(self.table_right)

        vlayout.addWidget(splitter)
        self.setLayout(vlayout)

    def update_right_table(self):
        row = 0
        self.table_right.setRowCount(0)

        if self.settings.selected_event not in self.settings.event_intervals:
            return

        interval = self.settings.event_intervals[self.settings.selected_event]
        for id in interval.interesting_ids:
            self.table_right.insertRow(row)
            self.table_right.setItem(row, 0, QTableWidgetItem(f"{id:03X}"))
            row += 1

    def on_detection_mode_changed(self):
        self.update_right_table()

    def on_isolation_forest_clicked(self):
        interval = self.settings.event_intervals[self.settings.selected_event]
        event_frames = self.settings.all_frames[interval.start_index:interval.end_index]

        data = likelihood_from_frames(
            "output/training-export.csv",
            event_frames,
            interval.interesting_ids)
        
        columns = data.columns.tolist()
        rows = data.values.tolist()

        self.table_left.setColumnCount(len(columns))
        self.table_left.setRowCount(len(rows))
        self.table_left.setHorizontalHeaderLabels(columns)

        for i, row in enumerate(rows):
            self.table_left.setItem(i, 0, QTableWidgetItem(f"{row[0]:.0f}"))
            self.table_left.setItem(i, 1, QTableWidgetItem(f"{int(row[1]):03X}"))
            self.table_left.setItem(i, 2, QTableWidgetItem(f"{row[2]:.0f}"))
            self.table_left.setItem(i, 3, QTableWidgetItem(f"{row[3]:.0f}"))
            self.table_left.setItem(i, 4, QTableWidgetItem(f"{row[4]:.0f}"))
            self.table_left.setItem(i, 5, QTableWidgetItem(f"{row[5]:.0f}"))
            self.table_left.setItem(i, 6, QTableWidgetItem(f"{row[6]:.0f}"))
            self.table_left.setItem(i, 7, QTableWidgetItem(f"{row[7]:.0f}"))
            self.table_left.setItem(i, 8, QTableWidgetItem(f"{row[8]:.0f}"))
            self.table_left.setItem(i, 9, QTableWidgetItem(f"{row[9]:.0f}"))
            self.table_left.setItem(i, 10, QTableWidgetItem(f"{row[10]:.0f}"))
            self.table_left.setItem(i, 11, QTableWidgetItem(f"{row[11]:.4f}"))
            self.table_left.setItem(i, 12, QTableWidgetItem(f"{row[12]:.1f}"))

    def on_event_clicked(self, event_name: str):
        self.update_right_table()
