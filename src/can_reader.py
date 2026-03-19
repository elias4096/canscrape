import csv, time
import can

from typing import List
from PySide6.QtCore import QThread, Signal


class CanReader(QThread):
    msg_signal = Signal(object)

    def __init__(self, interface: str = "", channel: str = "", bitrate: int = 0, csv_path: str = ""):
        super().__init__()
        self.interface = interface
        self.channel = channel
        self.bitrate = bitrate
        self.csv_path = csv_path
        self.running = True

    def run(self):
        if self.csv_path == "": # Live can reading
            try:
                bus: can.BusABC = can.Bus(interface=self.interface, channel=self.channel, bitrate=self.bitrate)
            except Exception as e:
                print("Failed to read CAN:", e)
                return

            while self.running:
                msg = bus.recv(1.0)
                if msg:
                    self.msg_signal.emit(msg)
        else: # CSV can reading
            try:
                # Assumed CSV format: Time Stamp,ID,Extended,Dir,Bus,LEN,D1,D2,D3,D4,D5,D6,D7,D8
                with open(self.csv_path) as f:
                    for row in csv.DictReader(f):
                        if not self.running:
                            break

                        ts = float(row["Time Stamp"]) / 1_000_000.0
                        id = int(row["ID"], 16)
                        extended = bool(row["Extended"].strip().lower() == "true")
                        dlc = int(row["LEN"])

                        data: List[int] = []
                        for i in range(1, 9):
                            cell = row[f"D{i}"].strip()
                            data.append(int(cell, 16) if cell else 0)

                        msg = can.Message(
                            timestamp=ts,
                            arbitration_id=id,
                            is_extended_id=extended,
                            dlc=dlc,
                            data=bytearray(data),
                            is_rx=True
                        )

                        self.msg_signal.emit(msg)
                        time.sleep(0.00001) # Hardcoded
            except Exception as e:
                print("Failed to read CSV file:", e)

    def stop(self):
        self.running = False