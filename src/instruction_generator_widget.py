import sys
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QCheckBox, QLabel, QPushButton, QTextEdit
)

# ---------------- HELPERS ----------------
def interface(text):
    return f"[INSPECTOR] {text}"

def event(text):
    return f"[EVENT] {text}"

# ---------------- DATA ----------------
OUTSIDE_ORDER = [
    "driver_door",
    "passenger_door",
    "rear_left_door",
    "rear_right_door"
]

INSIDE_DRIVER_ORDER = [
    "hazard_lights",
    "foot_brake",
    "wipers",
    "driver_seatbelt"
]

INSIDE_PASSENGER_ORDER = [
    "passenger_seatbelt"
]

EVENT_NAMES = {
    "driver_door": "Driver Door",
    "passenger_door": "Passenger Door",
    "rear_left_door": "Rear Left Door",
    "rear_right_door": "Rear Right Door",
    "hazard_lights": "Hazard Lights",
    "foot_brake": "Foot Brake",
    "wipers": "Wipers",
    "driver_seatbelt": "Driver seatbelt",
    "passenger_seatbelt": "Passenger Seatbelt"
}

DOOR_TEXT = {
    "driver_door": "Öppna och stäng förardörren tre till fyra gånger.",
    "passenger_door": "Öppna och stäng <b>höger dörr fram</b> tre till fyra gånger.",
    "rear_left_door": "Öppna och stäng <b>vänster dörr bak</b> tre till fyra gånger.",
    "rear_right_door": "Öppna och stäng <b>höger dörr bak</b> tre till fyra gånger."
}

INSIDE_DRIVER_TEXT = {
    "hazard_lights": "Slå på och av varningsblinkers tre till fyra gånger.",
    "foot_brake": "Tryck ned fotbromsen tre till fyra gånger.",
    "wipers": "Aktivera vindrutetorkarna tre till fyra gånger.",
    "driver_seatbelt": "Sätt på och ta av förarens säkerhetsbälte tre till fyra gånger."
}

PASSENGER_TEXT = {
    "passenger_seatbelt": "Sätt på och ta av fram-passagerarens säkerhetsbälte tre till fyra gånger."
}

# ---------------- LOGIC ----------------
def generate_instructions(selected):
    instructions = []
    instruction_pairs = []

    def add_step(interface_text, event_text):
        instruction_pairs.append({
            "interface": interface_text,
            "event": event_text
        })
        instructions.append(interface(interface_text))
        instructions.append(event(event_text))

    # -------- DRIVER --------
    driver_actions = [x for x in INSIDE_DRIVER_ORDER if x in selected]
    has_driver_door = "driver_door" in selected

    if has_driver_door:
        name = EVENT_NAMES["driver_door"]

        if driver_actions:
            add_step(
                f"Klicka på eventet <b>{name}</b>",
                "Öppna och stäng förardörren tre till fyra gånger, lämna den öppen, sätt dig i förarsätet, och stäng sedan dörren."
            )
        else:
            add_step(
                f"Klicka på eventet <b>{name}</b>",
                DOOR_TEXT["driver_door"]
            )

        for action in driver_actions:
            name = EVENT_NAMES[action]
            add_step(
                f"Klicka på eventet <b>{name}</b>",
                INSIDE_DRIVER_TEXT[action]
            )

        if driver_actions:
            add_step(
                f"Klicka på eventet <b>{EVENT_NAMES['driver_door']}</b>",
                "Öppna förardörren och kliv ut, öppna och stäng sedan dörren tre till fyra gånger och lämna den stängd när du är klar."
            )

    elif driver_actions:
        for action in driver_actions:
            name = EVENT_NAMES[action]
            add_step(
                f"Klicka på eventet <b>{name}</b>",
                INSIDE_DRIVER_TEXT[action]
            )

    # -------- PASSENGER --------
    passenger_actions = [x for x in INSIDE_PASSENGER_ORDER if x in selected]
    has_passenger_door = "passenger_door" in selected

    if has_passenger_door and passenger_actions:
        passenger_door_name = EVENT_NAMES["passenger_door"]

        add_step(
            f"Klicka på eventet <b>{passenger_door_name}</b>",
            "Öppna och stäng <b>höger dörr fram</b> tre till fyra gånger, lämna den öppen, sätt dig i fram-passagerarsätet, och stäng sedan dörren."
        )

        for action in passenger_actions:
            name = EVENT_NAMES[action]
            add_step(
                f"Klicka på eventet <b>{name}</b>",
                PASSENGER_TEXT[action]
            )

        add_step(
            f"Klicka på eventet <b>{passenger_door_name}</b>",
            "Öppna <b>höger dörr fram</b> och kliv ut, öppna och stäng sedan dörren tre till fyra gånger och lämna den stängd när du är klar."
        )

    elif passenger_actions:
        for action in passenger_actions:
            name = EVENT_NAMES[action]
            add_step(
                f"Klicka på eventet <b>{name}</b>",
                PASSENGER_TEXT[action]
            )

    # -------- ÖVRIGA DÖRRAR --------
    for door in OUTSIDE_ORDER:
        if door in ["driver_door", "passenger_door"]:
            continue

        if door in selected:
            name = EVENT_NAMES[door]
            add_step(
                f"Klicka på eventet <b>{name}</b>",
                DOOR_TEXT[door]
            )

    # front passenger door standalone
    if has_passenger_door and not passenger_actions:
        name = EVENT_NAMES["passenger_door"]
        add_step(
            f"Klicka på eventet <b>{name}</b>",
            DOOR_TEXT["passenger_door"]
        )

    return instructions, instruction_pairs


# ---------------- UI ----------------
class InstructionGeneratorWidget(QWidget):
    next_clicked = Signal()

    def __init__(self, settings=None):
        super().__init__()
        self.settings = settings
        self.setWindowTitle("Instruction Generator")

        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        title = QLabel("Select all signals you would like to identify from the list below:")
        title.setWordWrap(True)
        title.setStyleSheet("font-size: 13px; color: #cccccc; margin-bottom: 8px;")
        layout.addWidget(title)

        self.checkboxes = {}
        for key, label in [
            ("driver_door", "Driver Door"),
            ("passenger_door", "Passenger Door"),
            ("rear_left_door", "Rear Left Door"),
            ("rear_right_door", "Rear Right Door"),
            ("hazard_lights", "Hazard Lights"),
            ("foot_brake", "Foot Brake"),
            ("wipers", "Wipers"),
            ("driver_seatbelt", "Driver Seatbelt"),
            ("passenger_seatbelt", "Passenger Seatbelt")
        ]:
            cb = QCheckBox(label)
            self.checkboxes[key] = cb
            layout.addWidget(cb)

        btn = QPushButton("Next →")
        btn.clicked.connect(self._on_next)

        layout.addWidget(btn)
        self.setLayout(layout)

    def _on_next(self):
        selected = {k for k, cb in self.checkboxes.items() if cb.isChecked()}
        if self.settings is not None:
            self.settings.selected_events = selected
        self.next_clicked.emit()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = InstructionGeneratorWidget()
    w.show()
    sys.exit(app.exec())