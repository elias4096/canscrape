from dataclasses import dataclass
from typing import List

from PySide6.QtWidgets import QLabel

@dataclass
class CanFrame:
    time: float
    cnt: int
    len: int
    data: bytearray

    row: int
    noise_bits: List[List[bool]]
    event_bits: List[List[bool]]
    bytes_label: QLabel | None = None
    bits_label: QLabel | None = None

@dataclass
class SimpleCanFrame:
    time_stamp: float
    id: int
    len: int
    d1: int
    d2: int
    d3: int
    d4: int
    d5: int
    d6: int
    d7: int
    d8: int

@dataclass
class TrainingCanFrame:
    id: int
    d1: int
    d2: int
    d3: int
    d4: int
    d5: int
    d6: int
    d7: int
    d8: int

@dataclass
class EventInterval:
    start_index: int
    end_index: int
    interesting_ids: List[int]