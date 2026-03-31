from PySide6.QtWidgets import (
    QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)
from can import Message

from can_reader import CanReader
from models import CanFrame, SimpleCanFrame
from settings import DetectionMode, InputMode, Settings

class DataWidget(QWidget):
    def __init__(self, settings_model: Settings):
        super().__init__()
        self.settings = settings_model
        self.settings.inputModeChanged.connect(self.on_input_mode_changed)

        layout = QVBoxLayout()

        headers = ["Time Stamp","ID","Count","Length","Bytes","Bits"]
        self.table = QTableWidget(0, len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setAlternatingRowColors(True)
        self.table.resizeColumnsToContents()
        self.table.setColumnWidth(4, 150)
        self.table.setColumnWidth(5, 425)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)
        
        self.setLayout(layout)

    def on_input_mode_changed(self, mode: InputMode):
        # Todo: make channel & bitrate user adjustable
        if mode == InputMode.Off:
            self.stop_reader()
        elif mode == InputMode.PeakCan:
            self.settings.reader = CanReader("pcan", "PCAN_USBBUS1", 500_000)
        elif mode == InputMode.SerialPort:
            self.settings.reader = CanReader("slcan", "COM9", 500_000)
        elif mode == InputMode.CsvReplay:
            self.settings.reader = CanReader(csv_path=self.settings.csv_filepath)

        if self.settings.reader:
            self.table.setRowCount(0)
            self.settings.initial_timestamp = 0.0
            self.settings.current_timestamp = 0.0
            self.settings.frame_count = 0
            self.settings.frames.clear()
            self.settings.all_frames.clear()
            self.settings.reader.msg_signal.connect(self.update_table)
            self.settings.reader.start()

    def stop_reader(self):
        if self.settings.reader:
            self.settings.reader.stop()
            self.settings.reader.wait()
            self.settings.reader = None

    def update_table(self, msg: Message):
        if self.settings.initial_timestamp <= 0.0:
            self.settings.initial_timestamp = msg.timestamp

        self.settings.current_timestamp = msg.timestamp - self.settings.initial_timestamp
        self.settings.frame_count += 1

        if msg.arbitration_id not in self.settings.frames:
            row = self.table.rowCount()
            self.table.insertRow(row)

            bytes_label = QLabel(parent=self.table)
            bits_label = QLabel(parent=self.table)
            self.table.setCellWidget(row, 4, bytes_label)
            self.table.setCellWidget(row, 5, bits_label)

            noise_bits = [[False] * 8 for _ in range(msg.dlc)]
            event_bits = [[False] * 8 for _ in range(msg.dlc)]

            frame = CanFrame(
                time=self.settings.current_timestamp,
                cnt=1,
                len=msg.dlc,
                data=msg.data,
                row=row,
                noise_bits=noise_bits,
                event_bits=event_bits,
                bytes_label=bytes_label,
                bits_label=bits_label
            )

            self.settings.frames[msg.arbitration_id] = frame
        else:
            frame = self.settings.frames[msg.arbitration_id]

        det = self.settings.detectionMode()
        old_data = frame.data
        new_data = msg.data

        length = min(len(old_data), len(new_data))

        if det in (DetectionMode.Noise, DetectionMode.Event):
            for i in range(length):
                diff = old_data[i] ^ new_data[i]  # XOR → flipped bits
                if diff != 0:
                    for bit in range(8):
                        if diff & (1 << (7 - bit)):
                            if frame.noise_bits[i][bit]:
                                continue

                            if det == DetectionMode.Noise:
                                frame.noise_bits[i][bit] = True
                            elif det == DetectionMode.Event:
                                frame.event_bits[i][bit] = True

        frame.time = self.settings.current_timestamp
        frame.cnt += 1
        frame.len = msg.dlc
        frame.data = new_data


       
        data = list(msg.data)
        while len(data) < 8:
            data.append(0)

        self.settings.all_frames.append(SimpleCanFrame(
            msg.timestamp,
            msg.arbitration_id,
            msg.dlc,
            *data  # clean and safe
        ))



        self.table.setItem(frame.row, 0, QTableWidgetItem(f"{self.settings.current_timestamp:.3f}"))
        self.table.setItem(frame.row, 1, QTableWidgetItem(f"{msg.arbitration_id:03X}"))
        self.table.setItem(frame.row, 2, QTableWidgetItem(str(frame.cnt)))
        self.table.setItem(frame.row, 3, QTableWidgetItem(str(msg.dlc)))

        bytes_html = ""
        for i in range(msg.dlc):
            text = f"{msg.data[i]:02X}"

            if any(frame.noise_bits[i]):
                color = "red"
            elif any(frame.event_bits[i]):
                color = "blue"
            else:
                color = "white"

            bytes_html += f'<span style="color:{color}; margin-right:6px">{text}</span> '

        if frame.bytes_label:
            frame.bytes_label.setText(bytes_html)

        bits_html = ""
        for byte_i in range(msg.dlc):
            text = f"{msg.data[byte_i]:08b}"

            for bit_pos, bit_char in enumerate(text):
                if frame.noise_bits[byte_i][bit_pos]:
                    color = "red"
                elif frame.event_bits[byte_i][bit_pos]:
                    color = "blue"
                else:
                    color = "white"

                bits_html += f'<span style="color:{color}">{bit_char}</span>'

            bits_html += " "

        if frame.bits_label:
            frame.bits_label.setText(bits_html)