from enum import Enum
from typing import Dict, List

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QButtonGroup

from can_reader import CanReader
from models import CanFrame, EventInterval, SimpleCanFrame

class InputMode(Enum):
    Off = 0
    PeakCAN = 1
    SerialPort = 2
    CsvReplay = 3

class DetectionMode(Enum):
    Off = 0
    Event = 1

class Settings(QObject):
    inputModeChanged = Signal(InputMode)
    detectionModeChanged = Signal(DetectionMode)
    onIsolationForestClicked = Signal()
    onEventClicked = Signal(str)
    clearData = Signal()
    loadCsvSnapshot = Signal(str)

    def __init__(self):
        super().__init__()
        # Public
        self.csv_filepath = str()
        self.serial_port: str = "COM9"
        self.baseline_path = str()
        self.baseline_is_recording: bool = False
        self.baseline_noise_bits: dict = {}  # { "ID": [bitnummer, ...] }
        self.reader: CanReader | None = None
        self.initial_timestamp: float = 0.0
        self.current_timestamp: float = 0.0
        self.last_export_baseline: str = ""
        self.last_export_raw: str = ""
        self.last_export_json: str = ""
        # Todo: rename to current_frame_index
        self.frame_count: int = 0
        self.frames: Dict[int, CanFrame] = {}
        self.all_frames: List[SimpleCanFrame] = []

        self.selected_events: set = set()
        self.selected_event = str()
        self._event_group_ref: "QButtonGroup | None" = None
        self.event_intervals: Dict[str, EventInterval] = {
            "Hazard Lights": EventInterval([], []),
            "Foot Brake": EventInterval([], []),
            "Wipers": EventInterval([], []),
            "Driver Door": EventInterval([], []),
            "Passenger Door": EventInterval([], []),
            "Rear Left Door": EventInterval([], []),
            "Rear Right Door": EventInterval([], []),
            "Driver seatbelt": EventInterval([], []),
            "Passenger Seatbelt": EventInterval([], []),
        }

        # Private
        self._input_mode = InputMode.Off
        self._detection_mode = DetectionMode.Off

    def setInputMode(self, mode: InputMode):
        if self._input_mode != mode:
            self._input_mode = mode
            self.inputModeChanged.emit(mode)

    def inputMode(self):
        return self._input_mode

    def setDetectionMode(self, mode: DetectionMode):
        if self._detection_mode != mode:
            self._detection_mode = mode
            self.detectionModeChanged.emit(mode)

    def detectionMode(self):
        return self._detection_mode

    def reset_event_bits(self):
        for frame in self.frames.values():
            frame.event_bits = [[False] * 8 for _ in range(frame.len)]