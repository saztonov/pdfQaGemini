"""Style methods for chat panel"""


class StylesMixin:
    """Mixin providing style methods for chat panel"""

    def _small_button_style(self) -> str:
        return """
            QPushButton {
                background-color: #374151;
                color: #9ca3af;
                border: none;
                border-radius: 4px;
                padding: 2px 10px;
                font-size: 10px;
            }
            QPushButton:hover { background-color: #4b5563; color: #e5e7eb; }
        """

    def _combo_style(self) -> str:
        return """
            QComboBox {
                background-color: #374151;
                color: #e5e7eb;
                border: 1px solid #4b5563;
                border-radius: 8px;
                padding: 6px 10px;
                font-size: 12px;
            }
            QComboBox:hover { background-color: #4b5563; }
            QComboBox::drop-down { border: none; width: 20px; }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #9ca3af;
                margin-right: 6px;
            }
            QComboBox QAbstractItemView {
                background-color: #1f2937;
                color: #e5e7eb;
                selection-background-color: #2563eb;
                border: 1px solid #4b5563;
                border-radius: 8px;
            }
        """
