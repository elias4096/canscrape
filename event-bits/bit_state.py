"""
bit_state.py
============
Läser en rå CAN-CSV direkt till en dict i minnet.
Ingen mellanfil, ingen polars.

Stödda format (detekteras automatiskt via headers):

  Format A – minimal:
      id, d1..d8  (decimala värden)

  Format B – med Extended-kolumn:
      Time Stamp, ID, Extended, Dir, Bus, LEN, D1..D8

  Format C – med Message Number:
      Message Number, Time Stamp, ID, LEN, D1..D8

Returnerar alltid:
    { "ID": (seen_0: int, seen_1: int) }
"""

import csv
from bit_processor import normalize_id

MASK_64 = (1 << 64) - 1

# Kända header-set (lowercase för jämförelse)
_HEADERS_A  = {"id", "d1", "d2", "d3", "d4", "d5", "d6", "d7", "d8"}
_HEADERS_B  = {"time stamp", "id", "extended", "dir", "bus", "len",
               "d1", "d2", "d3", "d4", "d5", "d6", "d7", "d8"}
_HEADERS_C  = {"message number", "time stamp", "id", "len",
               "d1", "d2", "d3", "d4", "d5", "d6", "d7", "d8"}


def _parse_byte(val: str) -> int:
    val = val.strip()
    try:
        return int(val)
    except ValueError:
        return int(val, 16)


def _row_to_bits(row: dict, d_keys: list[str]) -> int:
    """Konverterar D1–D8 (eller d1–d8) till ett 64-bitars heltal."""
    bits = 0
    for k in d_keys:
        bits = (bits << 8) | (_parse_byte(row[k]) & 0xFF)
    return bits


def compute_bit_state(input_file: str) -> dict:
    """
    Läser input_file och returnerar för varje normaliserat ID:
        (seen_0, seen_1)

    seen_0 – mask över bitar som NÅGONSIN varit 0
    seen_1 – mask över bitar som NÅGONSIN varit 1
    """
    state: dict[str, list[int]] = {}

    with open(input_file, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        headers_lower = {h.lower() for h in (reader.fieldnames or [])}

        # Detektera format
        if _HEADERS_B <= headers_lower:
            fmt = 'B'
            d_keys = ["D1","D2","D3","D4","D5","D6","D7","D8"]
        elif _HEADERS_C <= headers_lower:
            fmt = 'C'
            d_keys = ["D1","D2","D3","D4","D5","D6","D7","D8"]
        elif _HEADERS_A <= headers_lower:
            fmt = 'A'
            d_keys = ["d1","d2","d3","d4","d5","d6","d7","d8"]
        else:
            raise ValueError(f"Okänt format i {input_file}: {reader.fieldnames}")

        for row in reader:
            # Normalisera ID
            if fmt == 'B':
                id_val = normalize_id(row["ID"], extended=False)
            elif fmt == 'C':
                id_val = normalize_id(row["ID"], extended=False)
            else:
                id_val = format(int(row["id"]), '04X')

            entry = state.get(id_val)
            if entry is None:
                entry = [0, 0]
                state[id_val] = entry

            bits = _row_to_bits(row, d_keys)
            entry[0] |= (~bits) & MASK_64   # seen_0
            entry[1] |= bits                 # seen_1

    return {id_val: (s0, s1) for id_val, (s0, s1) in state.items()}