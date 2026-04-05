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
    noise_masks: List[int]
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
class EventInterval:
    intervals: List[tuple]  # list of (start_index, end_index) pairs
    interesting_ids: List[int]

    @property
    def start_index(self) -> int:
        return self.intervals[-1][0] if self.intervals else 0

    @property
    def end_index(self) -> int:
        return self.intervals[-1][1] if self.intervals else 0

    def open_interval(self, start: int):
        self.intervals.append((start, 0))

    def close_interval(self, end: int):
        if self.intervals and self.intervals[-1][1] == 0:
            start = self.intervals[-1][0]
            self.intervals[-1] = (start, end)