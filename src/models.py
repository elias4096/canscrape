from dataclasses import dataclass
from typing import List

from PySide6.QtWidgets import QLabel

from dot_widget import DotWidget


@dataclass
class CANFrame: # Todo: rename to CanFrame
    row: int
    noise1: List[bool]
    noise2: List[bool]

    # 8 bit flags per byte
    noise1_bits: List[List[bool]]
    noise2_bits: List[List[bool]]

    time: float
    ext: bool
    cnt: int
    len: int
    data: bytearray

    # The NEW per-row QLabel (never recreated)
    bits_label: QLabel | None = None

@dataclass
class CanFunction: # Todo: rename to CanEvent
    dot: DotWidget
    start_index: int
    end_index: int
    can_ids: List[int]

    def to_json(self) -> dict | None:
            if self.start_index <= 0.0 or self.end_index <= 0.0:
                 return None

            return {
                "start_index": self.start_index,
                "end_index": self.end_index,
            }

