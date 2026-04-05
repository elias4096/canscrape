from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from instruction_generator_widget import generate_instructions
from settings import DetectionMode, Settings


class InstructionPanelWidget(QWidget):
    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings
        self._pairs = []
        self._step = 0
        self._sub = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        header1 = QLabel("<b>Välj \"Detection Mode: On\" innan du börjar utföra instruktionerna i ett <span style='color:#81C784;'>[EVENT]</span>.</b>")
        header1.setWordWrap(True)
        header2 = QLabel("<b>När du är färdig med <span style='color:#81C784;'>eventets</span> instruktioner, välj \"Detection Mode: Off\"</b>")
        header2.setWordWrap(True)
        layout.addWidget(header1)
        layout.addWidget(header2)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #555;")
        layout.addWidget(line)

        self.label = QLabel()
        self.label.setWordWrap(True)
        self.label.setStyleSheet("font-size: 13px;")
        layout.addWidget(self.label)

        layout.addStretch()

        self.settings.onEventClicked.connect(self._on_event_clicked)
        self.settings.detectionModeChanged.connect(self._on_detection_mode_changed)

    def show_instructions(self):
        _, self._pairs = generate_instructions(self.settings.selected_events)
        self._step = 0
        self._sub = 0
        self._show_current()

    def _show_current(self):
        if self._step >= len(self._pairs):
            self.label.setText("<span style='color:#81C784;'>✔ Alla instruktioner slutförda.</span>")
            return

        pair = self._pairs[self._step]

        if self._sub == 0:
            self.label.setText(f"<span style='color:#4FC3F7; font-weight:bold;'>[INSPECTOR]</span> {pair['interface']}")
        else:
            self.label.setText(f"<span style='color:#81C784; font-weight:bold;'>[EVENT]</span> {pair['event']}")

    def _on_event_clicked(self, event_name: str):
        import re
        if not self._pairs:
            return
        if self._step < len(self._pairs) and self._sub == 0:
            expected = self._pairs[self._step]["interface"]
            match = re.search(r'<b>(.*?)</b>', expected)
            if match and match.group(1) == event_name:
                self._sub = 1
                self._lock_event_selection(True)
                self._show_current()

    def _on_detection_mode_changed(self, mode: DetectionMode):
        if not self._pairs:
            return
        if mode == DetectionMode.Off:
            self._lock_event_selection(False)
            self._step += 1
            self._sub = 0
            self._show_current()

    def _lock_event_selection(self, locked: bool):
        group = self.settings._event_group_ref
        if group is None:
            return
        for btn in group.buttons():
            if locked:
                if btn.isChecked():
                    btn.setStyleSheet("background-color: #c084fc; color: black;")
                else:
                    btn.setEnabled(False)
            else:
                btn.setEnabled(True)
                btn.setStyleSheet("")