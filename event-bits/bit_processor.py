"""
bit_processor.py
================
Ansvarar enbart för ID-normalisering av CAN-IDs.
Ingen fil-I/O, inga polars-beroenden.
"""


def normalize_id(raw_id: str, extended: bool) -> str:
    """
    Normaliserar ett rå hex-ID till korrekt format:
      - Standard (11-bit, extended=False) → 4 hex-siffror, t.ex. '00C3'
      - Extended (29-bit, extended=True)  → 8 hex-siffror, t.ex. '000000DE'
    """
    val = int(raw_id.strip(), 16)
    if extended:
        return format(val & 0x1FFFFFFF, '08X')
    else:
        return format(val & 0x7FF, '04X')