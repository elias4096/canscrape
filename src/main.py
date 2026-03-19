import sys
import can
from typing import Dict

from PySide6.QtGui import QBrush, QCloseEvent, QColor, Qt
from PySide6.QtWidgets import (
    QApplication, QDockWidget, QMainWindow, QTableWidget, QTableWidgetItem, QLabel
)

from can_reader import CanReader
from inspector_widget import InspectorWidget
from models import CANFrame


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CAN Scrape")

        self.can_frames: Dict[int, CANFrame] = {}
        self.running_noise1: bool = False
        self.running_noise2: bool = False
        self.initial_timestamp: float = 0.0
        self.current_timestamp: float = 0.0
        self.current_message_number: int = 0
        self.csv_path: str = ""
        self.reader: CanReader | None = None

        self.table = QTableWidget(0, 14)
        self.table.setHorizontalHeaderLabels([
            "Time Stamp", "ID", "Extended", "Count", "Length",
            "D1","D2","D3","D4","D5","D6","D7","D8","Bits (64)"
        ])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.resizeColumnsToContents()
        self.setCentralWidget(self.table)

        dock = QDockWidget("Inspector", self)
        self.inspector = InspectorWidget(self)
        dock.setWidget(self.inspector)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)


    def start_reader(self):
        self.stop_reader()

        if self.inspector.pcan_radio.isChecked():
            self.reader = CanReader(interface="pcan", channel="PCAN_USBBUS1", bitrate=500_000)
        elif self.inspector.serial_radio.isChecked():
            self.reader = CanReader("slcan", "COM9", 500_000)
        elif self.inspector.csv_radio.isChecked():
            self.reader = CanReader(csv_path=self.csv_path)

        if self.reader:
            self.reader.msg_signal.connect(self.update_table)
            self.reader.start()


    def stop_reader(self):
        if self.reader:
            self.reader.stop()
            self.reader.wait()
            self.reader = None


    def update_table(self, msg: can.Message):
        can_id = msg.arbitration_id
        self.current_message_number += 1

        if self.initial_timestamp <= 0.0:
            self.initial_timestamp = msg.timestamp

        elapsed = msg.timestamp - self.initial_timestamp
        self.current_timestamp = elapsed
        self.inspector.elapsed_label.setText(f"Elapsed time: {elapsed:.1f} s")

        if can_id not in self.can_frames:
            row = self.table.rowCount()
            self.table.insertRow(row)

            bits_label = QLabel(parent=self.table)
            self.table.setCellWidget(row, 13, bits_label)

            frame = CANFrame(
                row=row,
                noise1=[False] * msg.dlc,
                noise2=[False] * msg.dlc,
                noise1_bits=[[False] * 8 for _ in range(msg.dlc)],
                noise2_bits=[[False] * 8 for _ in range(msg.dlc)],
                time=elapsed,
                ext=msg.is_extended_id,
                cnt=1,
                len=msg.dlc,
                data=msg.data,
                bits_label=bits_label
            )

            self.can_frames[can_id] = frame

        else:
            frame = self.can_frames[can_id]
            frame.cnt += 1

        lim = min(len(msg.data), frame.len)

        for i in range(lim):
            old = frame.data[i]
            new = msg.data[i]
            # XOR (^) shows which bits flipped. 0 -> unchanged and 1 -> changed.
            diff = old ^ new

            # diff != 0 -> something changed
            if diff != 0 and (self.running_noise1 or self.running_noise2):
                # Go through each bit and check if it changed.
                for bit in range(8):
                    if diff & (1 << (7 - bit)):
                        if self.running_noise1:
                            frame.noise1_bits[i][bit] = True
                        if self.running_noise2:
                            frame.noise2_bits[i][bit] = True
                            if frame.noise1_bits[i][bit] == False:
                                if self.inspector.selected_function in self.inspector.status_dots:
                                    if can_id not in self.inspector.status_dots[self.inspector.selected_function].can_ids:
                                        self.inspector.status_dots[self.inspector.selected_function].can_ids.append(can_id)

        self.inspector.refresh_list_widget()

        frame.time = elapsed
        frame.ext = msg.is_extended_id
        frame.data = msg.data
        frame.len = msg.dlc

        row = frame.row

        self.table.setItem(row, 0, QTableWidgetItem(f"{msg.timestamp}"))
        self.table.setItem(row, 1, QTableWidgetItem(f"{can_id:03X}"))
        self.table.setItem(row, 2, QTableWidgetItem(str(frame.ext)))
        self.table.setItem(row, 3, QTableWidgetItem(str(frame.cnt)))
        self.table.setItem(row, 4, QTableWidgetItem(str(msg.dlc)))

        for i in range(msg.dlc):
            item = QTableWidgetItem(f"{msg.data[i]:02X}")
            if any(frame.noise1_bits[i]):
                item.setForeground(QBrush(QColor("red")))
            elif any(frame.noise2_bits[i]):
                item.setForeground(QBrush(QColor("blue")))
            self.table.setItem(row, 5 + i, item)

        html: str = ""

        for byte_index in range(min(msg.dlc, 8)):
            byte_val = msg.data[byte_index]
            bits = f"{byte_val:08b}"

            for bit_pos, bit_char in enumerate(bits):
                if frame.noise1_bits[byte_index][bit_pos]:
                    color = "red"
                elif frame.noise2_bits[byte_index][bit_pos]:
                    color = "blue"
                else:
                    color = "white"

                html += f'<span style="color:{color}">{bit_char}</span>'

            html += " "

        if frame.bits_label:
            frame.bits_label.setText(html)


    def clear(self):
        self.running_noise1 = False
        self.running_noise2 = False
        self.initial_timestamp = 0.0
        self.inspector.elapsed_label.setText("Elapsed time:")
        self.can_frames.clear()
        self.table.setRowCount(0)


    def closeEvent(self, e: QCloseEvent):
        self.stop_reader()
        super().closeEvent(e)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainWindow()
    w.resize(1280, 720)
    w.show()
    sys.exit(app.exec())
