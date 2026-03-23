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

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "Time Stamp", "ID", "Extended", "Count", "Length", "Bytes", "Bits"
        ])
        self.table.setAlternatingRowColors(True)
        self.table.resizeColumnsToContents()
        self.table.setColumnWidth(5, 150)
        self.table.setColumnWidth(6, 425)
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
            self.settings.reader.msg_signal.connect(self.update_table)
            self.settings.reader.start()

    def stop_reader(self):
        # Todo: reset settings variables
        if self.settings.reader:
            self.settings.reader.stop()
            self.settings.reader.wait()
            self.reader = None

    def update_table(self, msg: Message):
        settings = self.settings
        can_id = msg.arbitration_id

        # ------------------------------------------------------------
        # FRAME COUNTER AND TIMESTAMPING
        # ------------------------------------------------------------
        settings.frame_count += 1

        if settings.initial_timestamp <= 0.0:
            settings.initial_timestamp = msg.timestamp

        elapsed = msg.timestamp - settings.initial_timestamp
        settings.current_timestamp = elapsed

        # ------------------------------------------------------------
        # CREATE FRAME ENTRY IF FIRST TIME WE SEE THIS ID
        # ------------------------------------------------------------
        if can_id not in self.settings.frames:
            row = self.table.rowCount()
            self.table.insertRow(row)

            bytes_label = QLabel(parent=self.table)
            bits_label = QLabel(parent=self.table)

            self.table.setCellWidget(row, 5, bytes_label)
            self.table.setCellWidget(row, 6, bits_label)

            noise_bits = [[False] * 8 for _ in range(msg.dlc)]
            event_bits = [[False] * 8 for _ in range(msg.dlc)]

            frame = CanFrame(
                time=elapsed,
                ext=msg.is_extended_id,
                cnt=1,
                len=msg.dlc,
                data=msg.data,

                row=row,
                noise_bits=noise_bits,
                event_bits=event_bits,
                bytes_label=bytes_label,
                bits_label=bits_label
            )

            self.settings.frames[can_id] = frame
        else:
            frame = self.settings.frames[can_id]
            frame.cnt += 1

        # ------------------------------------------------------------
        # DETECTION MODE LOGIC
        # ------------------------------------------------------------
        det = settings.detectionMode()
        old_data = frame.data
        new_data = msg.data

        length = min(len(old_data), len(new_data))

        if det in (DetectionMode.Noise, DetectionMode.Event):
            for i in range(length):
                diff = old_data[i] ^ new_data[i]  # XOR → flipped bits
                if diff != 0:
                    for bit in range(8):
                        if diff & (1 << (7 - bit)):

                            # ---- RULE: Noise dominates ----
                            if frame.noise_bits[i][bit]:
                                # Already noise → cannot become event
                                continue

                            if det == DetectionMode.Noise:
                                frame.noise_bits[i][bit] = True

                            elif det == DetectionMode.Event:
                                # Only mark event if not already noise
                                frame.event_bits[i][bit] = True

        # ------------------------------------------------------------
        # UPDATE FRAME VALUES
        # ------------------------------------------------------------
        frame.time = elapsed
        frame.ext = msg.is_extended_id
        frame.data = new_data
        frame.len = msg.dlc

        row = frame.row

        self.settings.all_frames.append(SimpleCanFrame(
            msg.timestamp, msg.arbitration_id, msg.dlc,
            msg.data[0], msg.data[1], msg.data[2], msg.data[3],
            msg.data[4], msg.data[5], msg.data[6], msg.data[7]
        ))

        # ------------------------------------------------------------
        # FILL MAIN TABLE
        # ------------------------------------------------------------
        self.table.setItem(row, 0, QTableWidgetItem(f"{elapsed:.3f}"))
        self.table.setItem(row, 1, QTableWidgetItem(f"{can_id:03X}"))
        self.table.setItem(row, 2, QTableWidgetItem(str(frame.ext)))
        self.table.setItem(row, 3, QTableWidgetItem(str(frame.cnt)))
        self.table.setItem(row, 4, QTableWidgetItem(str(msg.dlc)))

        # ------------------------------------------------------------
        # BYTE LABEL
        # ------------------------------------------------------------
        bytes_html = ""

        for i in range(msg.dlc):
            byte_val = msg.data[i]
            txt = f"{byte_val:02X}"

            if any(frame.event_bits[i]):
                color = "blue"
            elif any(frame.noise_bits[i]):
                color = "red"
            else:
                color = "white"

            bytes_html += f'<span style="color:{color}; margin-right:6px">{txt}</span> '

        if frame.bytes_label:
            frame.bytes_label.setText(bytes_html)

        # ------------------------------------------------------------
        # BITS LABEL
        # ------------------------------------------------------------
        bits_html = ""

        for byte_i in range(msg.dlc):
            byte_val = msg.data[byte_i]
            bits = f"{byte_val:08b}"

            for bit_pos, bit_char in enumerate(bits):

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