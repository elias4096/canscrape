import csv
import traceback

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
        self.settings.clearData.connect(self.on_clear_data)
        self.settings.loadCsvSnapshot.connect(self.load_snapshot)

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

    def on_clear_data(self):
        self.table.setRowCount(0)
        self.settings.initial_timestamp = 0.0
        self.settings.current_timestamp = 0.0
        self.settings.frame_count = 0
        self.settings.frames.clear()
        self.settings.all_frames.clear()

    def on_input_mode_changed(self, mode: InputMode):
        if mode == InputMode.Off:
            self.stop_reader()
        elif mode == InputMode.PeakCAN:
            self.settings.reader = CanReader("pcan", "PCAN_USBBUS1")
        elif mode == InputMode.SerialPort:
            self.settings.reader = CanReader("slcan", self.settings.serial_port)
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

    # ------------------------------------------------------------------ #
    #  Normaliserad rad: { arb_id, ts, dlc, data_bytes }
    # ------------------------------------------------------------------ #

    @staticmethod
    def _normalize_row(row: dict[str, str], fieldnames: list[str]) -> dict:
        id_col  = "ID"          if "ID"         in fieldnames else "id"
        len_col = "LEN"         if "LEN"        in fieldnames else "len"
        ts_col  = "Time Stamp"  if "Time Stamp" in fieldnames else None
        hex_bytes = "D1" in fieldnames
        d_cols  = [f"D{i}" for i in range(1, 9)] if hex_bytes else [f"d{i}" for i in range(1, 9)]

        arb_id = int(row[id_col].strip(), 16) & 0x7FF

        dlc = int(row.get(len_col, 8) or 8)
        dlc = max(1, min(dlc, 8))

        data_bytes = bytearray()
        for col in d_cols:
            cell = row.get(col, "").strip()
            if not cell:
                data_bytes.append(0)
            elif hex_bytes:
                data_bytes.append(int(cell, 16) & 0xFF)
            else:
                data_bytes.append(int(cell) & 0xFF)

        ts = 0.0
        if ts_col and ts_col in row:
            try:
                ts = float(row[ts_col]) / 1_000_000.0
            except ValueError:
                ts = 0.0

        return {"arb_id": arb_id, "ts": ts, "dlc": dlc, "data_bytes": data_bytes}

    # ------------------------------------------------------------------ #
    #  Snapshot från färdig CSV
    # ------------------------------------------------------------------ #

    def load_snapshot(self, csv_path: str):
        try:
            self.on_clear_data()

            # Sista normaliserade raden per ID
            last: dict[int, dict] = {}

            with open(csv_path, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                fieldnames = list(reader.fieldnames or [])
                for row in reader:
                    normed = self._normalize_row(row, fieldnames)
                    last[normed["arb_id"]] = normed

            for normed in last.values():
                arb_id     = normed["arb_id"]
                ts         = normed["ts"]
                dlc        = normed["dlc"]
                data_bytes = normed["data_bytes"]

                table_row = self.table.rowCount()
                self.table.insertRow(table_row)

                bytes_label = QLabel(parent=self.table)
                bits_label  = QLabel(parent=self.table)
                self.table.setCellWidget(table_row, 4, bytes_label)
                self.table.setCellWidget(table_row, 5, bits_label)

                can_id_str  = format(arb_id, '04X')
                noise_bits  = [[False] * 8 for _ in range(dlc)]
                noise_masks = [0] * dlc
                for bit_num in self.settings.baseline_noise_bits.get(can_id_str, []):
                    byte_idx = (bit_num - 1) // 8
                    bit_idx  = (bit_num - 1) % 8
                    if byte_idx < dlc:
                        noise_bits[byte_idx][bit_idx] = True
                        noise_masks[byte_idx] |= (1 << (7 - bit_idx))

                frame = CanFrame(
                    time=ts,
                    cnt=1,
                    len=dlc,
                    data=data_bytes,
                    row=table_row,
                    noise_bits=noise_bits,
                    event_bits=[[False] * 8 for _ in range(dlc)],
                    noise_masks=noise_masks,
                    bytes_label=bytes_label,
                    bits_label=bits_label,
                )
                self.settings.frames[arb_id] = frame

                d = list(data_bytes)
                while len(d) < 8:
                    d.append(0)
                self.settings.all_frames.append(SimpleCanFrame(ts, arb_id, dlc, *d))
                self.settings.frame_count += 1

                self.table.setItem(table_row, 0, QTableWidgetItem(f"{ts:.3f}"))
                self.table.setItem(table_row, 1, QTableWidgetItem(f"{arb_id:03X}"))
                self.table.setItem(table_row, 2, QTableWidgetItem("1"))
                self.table.setItem(table_row, 3, QTableWidgetItem(str(dlc)))

                bytes_html = ""
                for i in range(dlc):
                    text  = f"{data_bytes[i]:02X}"
                    color = "red" if any(noise_bits[i]) else "white"
                    bytes_html += f'<span style="color:{color}; margin-right:6px">{text}</span> '
                bytes_label.setText(bytes_html)

                bits_html = ""
                for byte_i in range(dlc):
                    text = f"{data_bytes[byte_i]:08b}"
                    for bit_pos, bit_char in enumerate(text):
                        color = "red" if noise_bits[byte_i][bit_pos] else "white"
                        bits_html += f'<span style="color:{color}">{bit_char}</span>'
                    bits_html += " "
                bits_label.setText(bits_html)

        except Exception as e:
            print(f"load_snapshot error: {e}")
            traceback.print_exc()

    # ------------------------------------------------------------------ #

    def update_table(self, msg: Message):
        if self.settings.initial_timestamp <= 0.0:
            self.settings.initial_timestamp = msg.timestamp

        self.settings.current_timestamp = msg.timestamp - self.settings.initial_timestamp
        self.settings.frame_count += 1

        if msg.arbitration_id not in self.settings.frames:
            row = self.table.rowCount()
            self.table.insertRow(row)

            bytes_label = QLabel(parent=self.table)
            bits_label  = QLabel(parent=self.table)
            self.table.setCellWidget(row, 4, bytes_label)
            self.table.setCellWidget(row, 5, bits_label)

            noise_bits  = [[False] * 8 for _ in range(msg.dlc)]
            event_bits  = [[False] * 8 for _ in range(msg.dlc)]

            can_id_str  = format(msg.arbitration_id & 0x7FF, '04X')
            noise_masks = [0] * msg.dlc
            for bit_num in self.settings.baseline_noise_bits.get(can_id_str, []):
                byte_idx = (bit_num - 1) // 8
                bit_idx  = (bit_num - 1) % 8
                if byte_idx < msg.dlc:
                    noise_bits[byte_idx][bit_idx] = True
                    noise_masks[byte_idx] |= (1 << (7 - bit_idx))

            frame = CanFrame(
                time=self.settings.current_timestamp,
                cnt=1,
                len=msg.dlc,
                data=msg.data,
                row=row,
                noise_bits=noise_bits,
                event_bits=event_bits,
                noise_masks=noise_masks,
                bytes_label=bytes_label,
                bits_label=bits_label,
            )
            print(msg.arbitration_id)
            self.settings.frames[msg.arbitration_id] = frame
        else:
            frame = self.settings.frames[msg.arbitration_id]

        det      = self.settings.detectionMode()
        old_data = frame.data
        new_data = msg.data
        length   = min(len(old_data), len(new_data), len(frame.noise_masks))

        if det == DetectionMode.Event:
            for i in range(length):
                diff = (old_data[i] ^ new_data[i]) & ~frame.noise_masks[i] & 0xFF
                if diff == 0:
                    continue
                for bit in range(8):
                    if diff & (1 << (7 - bit)):
                        frame.event_bits[i][bit] = True

        frame.time  = self.settings.current_timestamp
        frame.cnt  += 1
        frame.len   = msg.dlc
        frame.data  = new_data

        data = list(msg.data)
        while len(data) < 8:
            data.append(0)
        self.settings.all_frames.append(SimpleCanFrame(
            msg.timestamp, msg.arbitration_id, msg.dlc, *data
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