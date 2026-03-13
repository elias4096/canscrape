from typing import Dict, List, Tuple
from enum import Enum

# Todo:
# Read .csv files and let user choose frame count

class ByteType(Enum):
    RED = "\033[31m"
    GREEN = "\033[32m"
    BLUE = "\033[34m"
    YELLOW = "\033[33m"
    RESET = "\033[0m"

def read_data_file(filename: str) -> Dict[int, List[Tuple[int, ByteType]]]:
    result: Dict[int, List[Tuple[int, ByteType]]] = {}

    with open(filename, 'r') as f:
        for line in f:
            line = line.strip()

            if not line:
                continue

            # Data format: ID,LEN,B1,B2,B3,B4,B5,B6,B7,B8
            columns: List[str] = line.split(',')

            id: int = int(columns[0], 16)
            length: int = int(columns[1])

            raw_bytes: List[int] = [int(b, 16) for b in columns[2:2 + length]]
            colored_bytes: List[Tuple[int, ByteType]] = [(b, ByteType.RESET) for b in raw_bytes]

            result[id] = colored_bytes

    return result

def run():
    s1: Dict[int, List[Tuple[int, ByteType]]] = read_data_file("data_1.txt")
    s2: Dict[int, List[Tuple[int, ByteType]]] = read_data_file("data_2.txt")
    s3: Dict[int, List[Tuple[int, ByteType]]] = read_data_file("data_3.txt")

    result: Dict[int, List[Tuple[int, ByteType]]] = {}

    for pair in s2.items():
            key, value = pair
            result[key] = value

            # Detect noise between s1 and s2
            if key in s1:
                for (index, byte) in enumerate(value):
                    if byte != s1[key][index]:
                        result[key][index] = (byte[0], ByteType.RED)

    for pair in s3.items():
            key, value = pair

            if key not in s2:
                result[key] = [(b[0], ByteType.YELLOW) for b in value]
            else:
                # Detect byte change between s2 and s3
                for (index, byte) in enumerate(value):
                    if result[key][index][1] != ByteType.RESET:
                        continue

                    if byte != s2[key][index]:
                        result[key][index] = (byte[0], ByteType.BLUE)

    print_snapshot(result)

def print_snapshot(snapshot: Dict[int, List[Tuple[int, ByteType]]]) -> None:
    for index, item in enumerate(snapshot.items()):
        key, value = item

        formatted_bytes: List[str] = [f"{color.value}{byte:02X}{ByteType.RESET.value}" for byte, color in value]

        print(f"{index + 1}. ID: {key:03X}, Data: {' '.join(formatted_bytes)}")

if __name__ == "__main__":
    run()
