import csv
import json
import os
from typing import Dict, List

from models import EventInterval, SimpleCanFrame

def get_unique_filepath(path: str) -> str:
    """
    Returns a unique file path. If the file already exists,
    appends _2, _3, ... before the file extension.

    Example:
        data.csv -> data_2.csv -> data_3.csv
    """
    directory, filename = os.path.split(path)
    name, extension = os.path.splitext(filename)

    counter = 2
    candidate = path

    while os.path.exists(candidate):
        candidate = os.path.join(directory, f"{name}_{counter}{extension}")
        counter += 1

    return candidate

def baseline_csv_export(frames: List[SimpleCanFrame], filename: str):
    filename = get_unique_filepath(filename)

    # ID,D1,D2,D3,D4,D5,D6,D7,D8
    header = ["id","d1","d2","d3","d4","d5","d6","d7","d8"]

    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)

        for frame in frames:
            writer.writerow([frame.id, frame.d1, frame.d2, frame.d3, frame.d4, frame.d5, frame.d6, frame.d7, frame.d8])

    return filename

def raw_csv_export(frames: List[SimpleCanFrame], filename: str):
    filename = get_unique_filepath(filename)

    # Time Stamp,ID,Extended,Dir,Bus,LEN,D1,D2,D3,D4,D5,D6,D7,D8
    header = ["Time Stamp","ID","Extended","Dir","Bus","LEN","D1","D2","D3","D4","D5","D6","D7","D8"]

    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)

        for frame in frames:
            writer.writerow([f"{frame.time_stamp * 1_000_000:.0f}", f"{frame.id:08X}", "false", "Rx", "0", frame.len,
                             f"{frame.d1:02X}", f"{frame.d2:02X}", f"{frame.d3:02X}", f"{frame.d4:02X}",
                             f"{frame.d5:02X}", f"{frame.d6:02X}", f"{frame.d7:02X}", f"{frame.d8:02X}"])

    return filename

def event_indexes_json_export(event_intervals: Dict[str, EventInterval], filename: str):
    filename = get_unique_filepath(filename)

    serializable = {
        key: {
            "start_index": interval.start_index,
            "end_index": interval.end_index
        }
        for key, interval in event_intervals.items()
        if interval.start_index != 0 and interval.end_index != 0
    }

    with open(filename, "w") as f:
        json.dump(serializable, f, indent=4)

    return filename