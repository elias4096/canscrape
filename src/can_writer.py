import csv
import json
from typing import Dict

from models import CANFrame, CanFunction


def export_frames_to_csv(frames: Dict[int, CANFrame], filename: str = "output.csv") -> None:
    header = ["Message Number","Time Offset (ms)","ID","LEN","D1","D2","D3","D4","D5","D6","D7","D8"]

    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)

        for i, (key, value) in enumerate(frames.items()):
            data_bytes = [f"{b:02X}" for b in value.data]
            data_bytes += [""] * (8 - len(data_bytes))

            writer.writerow([i + 1, f"{value.time:.4f}", f"{key:03X}", value.len, *data_bytes])

def export_events_to_json(data: Dict[str, CanFunction]) -> None:
    serializable = {}

    for key, value in data.items():
        json_data = value.to_json()
        if (json_data is not None):
            serializable[key] = json_data


    with open("output.json", "w") as f:
        json.dump(serializable, f, indent=4)
