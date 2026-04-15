import csv
import time
import can
from typing import List
from PySide6.QtCore import QThread, Signal

class CanReader(QThread):
    msg_signal = Signal(object)

    def __init__(self, interface: str = "", channel: str = "", csv_path: str = ""):
        super().__init__()
        self.interface = interface
        self.channel = channel
        self.csv_path = csv_path
        self.running = True
        self.bitrates = [
            500_000, 1_000_000, 125_000, 250_000, 100_000, 83_300, 20_000, 50_000, 10_000, 5_000
        ]

    def run(self):
        if self.csv_path == "":  # Live CAN reading
            #self.bitrate = self.detect_bitrate()
            self.bitrate = 125_000
            if self.bitrate is None:
                print("Failed to detect any valid bitrate.")
                return

            try:
                bus: can.BusABC = can.Bus(interface=self.interface, channel=self.channel, bitrate=self.bitrate)
            except Exception as e:
                print("Failed to read CAN:", e)
                return

            while self.running:
                msg = bus.recv(1.0)
                if msg:
                    self.msg_signal.emit(msg)
        else:  # CSV CAN reading
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
                        time.sleep(0.00001)  # Hardcoded
            except Exception as e:
                print("Failed to read CSV:", e)

    def detect_bitrate(self):
        for bitrate in self.bitrates:
            try:
                bus = can.Bus(interface=self.interface, channel=self.channel, bitrate=bitrate)
                print(f"Testing bitrate: {bitrate / 1_000} kbit/s")
                msg = bus.recv(1.0)
                if msg:
                    print(f"Detected valid bitrate: {bitrate / 1_000} kbit/s")
                    return bitrate
                bus.shutdown()
            except Exception as e:
                print(f"Failed to test bitrate {bitrate / 1_000} kbit/s: {e}")
        return None

    def stop(self):
        self.running = False
