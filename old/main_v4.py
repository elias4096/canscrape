from dataclasses import dataclass
from typing import Dict, List, Tuple
from enum import Enum
import csv

# Ideas:
# Make use of more snapshots, maybe user can choose amount of snapshots?
# Sort output based on findings

# Improve data filtering/sorting with pandas
# https://pandas.pydata.org/docs/index.html

# Find byte changes with:
# Clustering (k-means, DBSCAN)
# Dimensionality Reduction (PCA, t-SNE)
# Anomaly Detection (Isolation Forest, One-Class SVM)
# https://scikit-learn.org/stable/

# Improve noise detection by using isolation Forest algorithm (PyOD)
# https://github.com/yzhao062/pyod

class ConsoleColor(Enum):
    RED = "\033[31m"
    GREEN = "\033[32m"
    BLUE = "\033[34m"
    YELLOW = "\033[33m"
    RESET = "\033[0m"

@dataclass
class CANFrame:
    time_stamp: int
    id: int
    ext: str
    dir: str
    bus: int
    cnt: int
    len: int
    bytes: List[Tuple[int, ConsoleColor]]

def read_data_file(filename: str, frame_count: int) -> Dict[int, CANFrame]:
    result: Dict[int, CANFrame] = {}

    with open(filename, mode ='r') as file:
        reader = csv.DictReader(file)

        frames_read: int = 0

        for row in reader:
            if frames_read >= frame_count:
                break

            time_stamp = int(row['Time Stamp'])
            id = int(row['ID'], 16)
            extended = row['Extended']
            direction = row['Dir']
            bus = int(row['Bus'])
            length = int(row['LEN'])
            
            raw_bytes: List[int] = [int(row.get(f"D{i}", ""), 16) for i in range(1, length + 1)]
            colored_bytes: List[Tuple[int, ConsoleColor]] = [(b, ConsoleColor.RESET) for b in raw_bytes]

            if id in result:
                result[id].time_stamp = time_stamp
                result[id].id = time_stamp
                result[id].ext = extended
                result[id].dir = direction
                result[id].bus = bus
                result[id].cnt += 1
                result[id].len = length
                result[id].bytes = colored_bytes
            else:
                result[id] = CANFrame(time_stamp, id, extended, direction, bus, 1, length, colored_bytes)

            frames_read += 1

    return result

def run():
    s1: Dict[int, CANFrame] = read_data_file("data.csv", 500)
    s2: Dict[int, CANFrame] = read_data_file("data.csv", 51000)
    s3: Dict[int, CANFrame] = read_data_file("data.csv", 52000)

    result: Dict[int, CANFrame] = {}

    for pair in s2.items():
        key, value = pair
        result[key] = value

        # Detect noise between s1 and s2
        if key in s1:
            for (index, byte) in enumerate(value.bytes):
                if byte != s1[key].bytes[index]:
                    result[key].bytes[index] = (byte[0], ConsoleColor.RED)

    for pair in s3.items():
        key, value = pair

        if key not in s2:
            result[key] = value
            result[key].bytes = [(b[0], ConsoleColor.YELLOW) for b in value.bytes]
        else:
            # Detect byte change between s2 and s3
            for (index, byte) in enumerate(value.bytes):
                if result[key].bytes[index][1] != ConsoleColor.RESET:
                    continue

                if byte != s2[key].bytes[index]:
                    result[key].bytes[index] = (byte[0], ConsoleColor.BLUE)

    print_snapshot(result)

def print_snapshot(snapshot: Dict[int, CANFrame]):
    for index, item in enumerate(snapshot.items()):
        key, value = item

        formatted_bytes: List[str] = [f"{color.value}{byte:02X}{ConsoleColor.RESET.value}" for byte, color in value.bytes]

        print(f"{index + 1}. Time: {value.time_stamp}, ID: {key:03X}, Ext: {value.ext}, Dir: {value.dir}, Bus: {value.bus}, Cnt: {value.cnt}, Len: {value.len}, Data: {' '.join(formatted_bytes)}")

if __name__ == "__main__":
    run()
