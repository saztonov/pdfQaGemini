"""HTML message rendering for chat panel"""
import re


class MessageRenderer:
    """Renders chat messages to HTML"""
    
    def __init__(self):
        self._collapsed_thoughts: set[int] = set()
    
    def set_collapsed_thoughts(self, collapsed: set[int]):
        """Set collapsed thoughts indices"""
        self._collapsed_thoughts = collapsed
    
    def toggle_thought(self, idx: int):
        """Toggle thought collapse state"""
        if idx in self._collapsed_thoughts:
            self._collapsed_thoughts.discard(idx)
        else:
            self._collapsed_thoughts.add(idx)
    
    def render_message(self, msg: dict, index: int) -> str:
        """Render a single message to HTML"""
        role = msg.get("role")
        content = msg.get("content", "")
        timestamp = msg.get("timestamp", "")
        meta = msg.get("meta", {})
        
        if role == "user":
            return self._render_user_message(content, timestamp)
        elif role == "thinking":
            return self._render_thinking_message(content, timestamp, index)
        elif role == "assistant":
            return self._render_assistant_message(content, timestamp, meta)
        elif role == "system":
            level = msg.get("level", "info")
            return self._render_system_message(content, timestamp, level)
        elif role == "thinking_progress":
            return self._render_thinking_progress(timestamp)
        return ""
    
    def _render_user_message(self, content: str, timestamp: str) -> str:
        return f"""
            <div style="margin: 12px 0; padding: 12px 16px; background-color: #f0f7ff; border: 1px solid #d0e4ff; border-radius: 16px;">
                <div style="font-weight: bold; color: #1976d2; margin-bottom: 6px; font-size: 12px;">
                    Вы <span style="color: #666; font-weight: normal;">{timestamp}</span>
                </div>
                <div style="color: #1a1a1a; font-size: 14px; line-height: 1.5;">{self._escape_html(content)}</div>
            </div>
        """
    
    def _render_thinking_message(self, content: str, timestamp: str, index: int) -> str:
        is_collapsed = index in self._collapsed_thoughts
        arrow = "▶" if is_collapsed else "▼"
        content_html = "" if is_collapsed else f"""<div style="color: #555; font-style: italic; font-size: 13px; line-height: 1.4; margin-top: 8px; background-color: #fafafa; padding: 8px; border-radius: 6px;">{self._format_markdown(content)}</div>"""
        return f"""
            <div style="margin: 8px 0; padding: 10px 14px; background-color: #f5f9f5; border: 1px solid #c8e6c9; border-radius: 12px; border-left: 3px solid #66bb6a;">
                <a href="toggle_thought:{index}" style="text-decoration: none; color: #43a047; font-size: 12px; cursor: pointer; font-weight: 500;">
                    {arrow} 💭 Размышления
                </a>
                {content_html}
            </div>
        """
    
    def _render_assistant_message(self, content: str, timestamp: str, meta: dict) -> str:
        meta_html = self._render_meta(meta)
        return f"""
            <div style="margin: 12px 0; padding: 12px 16px; background-color: #f9f9f9; border: 1px solid #e0e0e0; border-radius: 16px;">
                <div style="font-weight: bold; color: #2e7d32; margin-bottom: 6px; font-size: 12px;">
                    Gemini <span style="color: #666; font-weight: normal;">{timestamp}</span>
                </div>
                <div style="color: #1a1a1a; font-size: 14px; line-height: 1.5;">{self._format_markdown(content)}</div>
                {meta_html}
            </div>
        """
    
    def _render_system_message(self, content: str, timestamp: str, level: str) -> str:
        colors = {
            "info": ("#1976d2", "#e3f2fd", "#1a1a1a"),
            "success": ("#388e3c", "#e8f5e9", "#1a1a1a"),
            "warning": ("#f57c00", "#fff3e0", "#1a1a1a"),
            "error": ("#d32f2f", "#ffebee", "#1a1a1a"),
        }
        border_color, bg_color, text_color = colors.get(level, colors["info"])
        return f"""
            <div style="margin: 8px 0; padding: 8px 12px; background-color: {bg_color}; border: 1px solid {border_color}; border-radius: 8px;">
                <div style="font-size: 12px; color: {border_color};">
                    <span style="font-weight: bold;">Система</span> 
                    <span style="color: #666; font-size: 11px;">{timestamp}</span>
                </div>
                <div style="color: {text_color}; font-size: 13px; margin-top: 4px;">{self._escape_html(content)}</div>
            </div>
        """
    
    def _render_thinking_progress(self, timestamp: str) -> str:
        return f"""
            <div style="margin: 8px 0; padding: 10px 14px; background-color: #fffbf0; border: 1px solid #ffe082; border-radius: 12px; border-left: 3px solid #ffa726;">
                <div style="font-size: 12px; color: #ef6c00; margin-bottom: 4px;">
                    💭 Размышляю... <span style="color: #666;">{timestamp}</span>
                </div>
            </div>
        """
    
    def _render_meta(self, meta: dict) -> str:
        """Render meta info"""
        if not meta:
            return ""
        model = meta.get("model", "")
        thinking = meta.get("thinking_level", "")
        meta_parts = []
        if model:
            short_model = model.replace("gemini-3-", "").replace("-preview", "").title()
            meta_parts.append(short_model)
        if thinking:
            meta_parts.append(thinking.title())
        if meta_parts:
            return f"""<div style="font-size: 11px; color: #666; margin-top: 8px;">{' · '.join(meta_parts)}</div>"""
        return ""
    
    def _format_markdown(self, text: str) -> str:
        """Format markdown to HTML"""
        text = self._escape_html(text)
        # Bold: **text**
        text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
        # Italic: *text*
        text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)
        # Inline code: `code`
        text = re.sub(r'`([^`]+)`', r'<code style="background-color: #f5f5f5; padding: 2px 4px; border-radius: 3px; color: #d32f2f; border: 1px solid #e0e0e0;">\1</code>', text)
        # Links: [text](url)
        text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" style="color: #1976d2; text-decoration: underline;">\1</a>', text)
        return text
    
    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters"""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;")
            .replace("\n", "<br>")
        )
