from typing import Dict, List
from enum import Enum

# Todo:
# Read .csv files and let user choose frame count

def read_data_file(filename: str) -> Dict[str, List[str]]:
    result: Dict[str, List[str]] = {}

    with open(filename) as f:
        for line in f:
            # Data format: ID,LEN,B1,B2,B3,B4,B5,B6,B7,B8

            columns = line.split(',')

            id: str = columns[0]
            len: int = int(columns[1])
            bytes: List[str] = [b for b in columns[2:2 + len - 1]]

            result[id] = bytes

    return result

class ByteType(Enum):
    NONE = 1
    NOISE = 2
    CHANGED = 3

def run():
    RED = "\033[31m"
    GREEN = "\033[32m"
    BLUE = "\033[34m"
    YELLOW = "\033[33m"
    RESET = "\033[0m"

    s1: Dict[str, List[str]] = read_data_file("data_1.txt")
    s2: Dict[str, List[str]] = read_data_file("data_2.txt")
    s3: Dict[str, List[str]] = read_data_file("data_3.txt")

    result: Dict[str, List[str]] = {}

    for pair in s2.items():
        result[pair[0]] = pair[1]

        # Detect noise between s1 and s2
        if pair[0] in s1:
            for (i, b) in enumerate(pair[1]):
                if b != s1[pair[0]][i]:
                    pair[1][i] = f"{RED}{pair[1][i]}{RESET}"

    for pair in s3.items():
        if pair[0] not in s2:
            result[pair[0]] = [f"{BLUE}{b}{RESET}" for b in pair[1]]
        else:
            # Detect byte change between s2 and s3
            for (i, b) in enumerate(pair[1]):
                if b != s2[pair[0]][i]:
                    if RED not in result[pair[0]][i]:
                        result[pair[0]][i] = f"{BLUE}{pair[1][i]}{RESET}"
                    
    print_snapshot(result)

def print_snapshot(snapshot: Dict[str, List[str]]):
    for index, pair in enumerate(snapshot.items()):
        bytes_str: str = " ".join(pair[1]) + " "
        print(f"{index + 1}. ID: {pair[0]}, Data: {bytes_str}")


if __name__ == "__main__":
    run()
