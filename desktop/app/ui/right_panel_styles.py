"""Styles for RightContextPanel"""


class RightPanelStylesMixin:
    """Mixin with style methods for RightContextPanel"""

    def _button_style(self) -> str:
        return """
            QPushButton {
                background-color: #3e3e42;
                color: #cccccc;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #505054; color: #ffffff; }
            QPushButton:pressed { background-color: #0e639c; }
            QPushButton:disabled { background-color: #2d2d2d; color: #666; }
        """

    def _icon_button_style(self) -> str:
        return """
            QPushButton {
                background-color: #3e3e42;
                color: #cccccc;
                border: none;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #505054; color: #ffffff; }
            QPushButton:pressed { background-color: #0e639c; }
            QPushButton:disabled { background-color: #2d2d2d; color: #666; }
        """

    def _delete_all_button_style(self) -> str:
        return """
            QPushButton {
                background-color: #5a1a1a;
                color: #cccccc;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #7a2020; color: #ffffff; }
            QPushButton:pressed { background-color: #3a0a0a; }
            QPushButton:disabled { background-color: #2d2d2d; color: #666; }
        """
