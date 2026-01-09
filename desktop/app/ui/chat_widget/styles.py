"""Styles for chat widget components"""


def get_user_bubble_style() -> str:
    return """
        QFrame#bubble {
            background-color: #1e3a5f;
            border-radius: 12px;
            border-left: 3px solid #3b82f6;
        }
    """


def get_assistant_bubble_style() -> str:
    return """
        QFrame#bubble {
            background-color: #2d2d2d;
            border-radius: 12px;
        }
    """


def get_thinking_bubble_style() -> str:
    return """
        QFrame#bubble {
            background-color: #1a2e1a;
            border-radius: 12px;
            border-left: 3px solid #4ade80;
        }
    """


def get_system_bubble_style() -> str:
    return """
        QFrame#bubble {
            background-color: #1e3a5f;
            border-radius: 12px;
            border: 1px solid #3b82f6;
        }
    """


def get_loading_bubble_style() -> str:
    return """
        QFrame#bubble {
            background-color: #374151;
            border-radius: 12px;
            border-left: 3px solid #6b7280;
        }
    """


def get_default_bubble_style() -> str:
    return """
        QFrame#bubble {
            background-color: #374151;
            border-radius: 12px;
        }
    """


def get_header_style(role: str) -> str:
    if role == "user":
        return "color: #60a5fa; font-size: 12px; font-weight: bold;"
    elif role == "assistant":
        return "color: #4ade80; font-size: 12px; font-weight: bold;"
    elif role == "thinking":
        return "color: #86efac; font-size: 12px; font-weight: 500;"
    elif role == "system":
        return "color: #60a5fa; font-size: 12px; font-weight: bold;"
    return "color: #9ca3af; font-size: 12px; font-weight: bold;"


def get_content_style(role: str) -> str:
    if role == "user":
        return """
            QTextBrowser {
                background: transparent;
                border: none;
                color: #ffffff;
                font-size: 14px;
                line-height: 1.5;
            }
            QTextBrowser a { color: #bfdbfe; }
        """
    elif role == "thinking":
        return """
            QTextBrowser {
                background: transparent;
                border: none;
                color: #a7f3d0;
                font-size: 13px;
                font-style: italic;
                line-height: 1.4;
            }
        """
    return """
        QTextBrowser {
            background: transparent;
            border: none;
            color: #e5e7eb;
            font-size: 14px;
            line-height: 1.5;
        }
        QTextBrowser a { color: #60a5fa; }
        QTextBrowser code {
            background-color: #1f2937;
            color: #f87171;
            padding: 2px 6px;
            border-radius: 4px;
        }
    """


def get_scroll_area_style() -> str:
    return """
        QScrollArea {
            background-color: #1a1a1a;
            border: none;
        }
        QScrollArea > QWidget > QWidget {
            background-color: #1a1a1a;
        }
        QScrollBar:vertical {
            background-color: #1a1a1a;
            width: 10px;
            border-radius: 5px;
        }
        QScrollBar::handle:vertical {
            background-color: #404040;
            border-radius: 5px;
            min-height: 30px;
        }
        QScrollBar::handle:vertical:hover {
            background-color: #555;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0px;
        }
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
            background: none;
        }
    """
