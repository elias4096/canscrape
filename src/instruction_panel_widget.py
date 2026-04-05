from PySide6.QtWidgets import QTextEdit, QVBoxLayout, QWidget

from instruction_generator_widget import generate_instructions
from settings import Settings


class InstructionPanelWidget(QWidget):
    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.text = QTextEdit()
        self.text.setReadOnly(True)
        layout.addWidget(self.text)

    def show_instructions(self):
        _, pairs = generate_instructions(self.settings.selected_events)

        html = ""
        html += "<b>Välj \"Detection Mode: On\" innan du påbörjat ett <span style='color:#81C784;'>event</span>.</b><br>"
        html += "<b>När du är färdig med <span style='color:#81C784;'>eventets</span> instruktioner, välj \"Detection Mode: Off\"</b><br>"
        html += "<hr style='border:1px solid #555; margin-top:2px; margin-bottom:10px;'>"

        for step in pairs:
            html += f"<span style='color:#4FC3F7; font-weight:bold;'>[INSPECTOR]</span> {step['interface']}<br>"
            html += f"<span style='color:#81C784; font-weight:bold;'>[EVENT]</span> {step['event']}<br>"

        self.text.setHtml(html)