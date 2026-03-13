from typing import Dict, List, Set
from random import sample, randint

# Todo:
# Only update some of the rows when generating data files.
# During noise removal, only remove bytes instead of entire rows. 

def generate_data_files(row_count: int = 64) -> None:
    # IDs are usually 11 bits: 11111111111 = 2047 = 0x7FF
    ids: List[str] = [f"{randint(0, 0x7FF):03X}" for _ in range(row_count)]
    
    all_data: List[List[List[str]]] = []

    rows_to_update: Set[int] = set(sample(range(row_count), row_count // 2))
    
    for file_index in range(3):
        with open(f"simulated_data_{file_index}.txt", 'w') as f:
            current_data: List[List[str]] = []

            for row_index in range(row_count):
                if file_index == 0:
                    bytes: List[str] = [f"{randint(0, 0xFF):02X}" for _ in range(8)]
                else:
                    prev_bytes: List[str] = all_data[file_index - 1][row_index]
                    bytes = prev_bytes.copy()

                    if row_index in rows_to_update:
                        byte_indicies: List[int] = sample(range(8), randint(1, 3))

                        for byte_index in byte_indicies:
                            bytes[byte_index] = f"{randint(0, 0xFF):02X}"

                current_data.append(bytes)
                data_str: str = ' '.join(bytes)
                f.write(f"0x{ids[row_index]},{data_str}\n")

            all_data.append(current_data)

def read_data_file(filename: str) -> Dict[str, str]:
    result: Dict[str, str] = {}

    with open(filename) as f:
        for line in f:
            columns = line.split(',')
            result[columns[0]] = columns[1]

    return result

def non_ai_algorithm():
    l0: Dict[str, str] = read_data_file("simulated_data_0.txt")
    l1: Dict[str, str] = read_data_file("simulated_data_1.txt")
    l2: Dict[str, str] = read_data_file("simulated_data_2.txt")

    for pair in l0.items():
        if pair[0] not in l1:
            continue

        l0_bytes: List[str] = pair[1].split(' ')
        l1_bytes: List[str] = l1[pair[0]].split(' ')
        unchanged_bytes: List[str] = [""] * 8

        unchanged_byte_count: int = 8

        for byte_index in range(8):
            if l0_bytes[byte_index] == l1_bytes[byte_index]:
                unchanged_bytes[byte_index] = l0_bytes[byte_index]
                unchanged_byte_count -= 1

        l2_bytes: List[str] = l2[pair[0]].split(' ')
        interesting_bytes: List[str] = ["--"] * 8

        for byte_index in range(8):
            if unchanged_bytes[byte_index] == "":
                continue

            if l0_bytes[byte_index] != l2_bytes[byte_index]:
                interesting_bytes[byte_index] = l2_bytes[byte_index]

        bytes_str = ' '.join(interesting_bytes).replace("\n", "")
        if bytes_str == "-- -- -- -- -- -- -- --":
            continue

        # Noise is the number of bytes that changed between l0 and l1.
        print(f"ID: {pair[0]}, Data: {bytes_str}, Noise: {unchanged_byte_count}")

def main():
    while True:
        print("\n[1] Generate CAN data")
        print("[2] Run non-AI algorithm")
        print("[3] Close")

        number: str = input("")

        if number == '1':
            generate_data_files()
        elif number == '2':
            non_ai_algorithm()
        elif number == '3':
            break
        else:
            print("Invalid input")

if __name__ == "__main__":
    main()
