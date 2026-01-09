"""Trace display and formatting for inspector tab"""

import json
from app.services.trace import ModelTrace


def build_full_log(trace: ModelTrace, time_str: str) -> str:
    """Build full chronological log text

    Note: This is similar to model_inspector/trace_display.py:build_full_log
    Consider extracting to shared/ui_utils/trace_formatter.py in future refactoring.
    """
    lines = []

    lines.append("╔═══════════════════════════════════════════════════════════╗")
    lines.append("║              ПОЛНЫЙ ЛОГ ВЗАИМОДЕЙСТВИЯ С МОДЕЛЬЮ          ║")
    lines.append("╚═══════════════════════════════════════════════════════════╝")
    lines.append("")
    lines.append(f"═══ ЗАПРОС {trace.id[:8]} ═══")
    lines.append("")
    lines.append(f"⏰ Время: {time_str}")
    lines.append(f"📌 Модель: {trace.model}")
    lines.append(f"🧠 Thinking Level: {trace.thinking_level}")
    lines.append(f"⏱️ Latency: {trace.latency_ms:.2f} мс" if trace.latency_ms else "⏱️ Latency: —")
    lines.append(f"✅ Финальный: {'Да' if trace.is_final else 'Нет'}")
    lines.append(f"📁 Файлов: {len(trace.input_files)}")
    if trace.input_tokens is not None:
        lines.append(f"📥 Токены входа: {trace.input_tokens:,}")
    if trace.output_tokens is not None:
        lines.append(f"📤 Токены выхода: {trace.output_tokens:,}")
    if trace.total_tokens is not None:
        lines.append(f"📊 Всего токенов: {trace.total_tokens:,}")
    lines.append("")

    # System prompt
    lines.append("┌─────────────────────────────────────────────────────────────┐")
    lines.append("│ 📝 SYSTEM PROMPT                                            │")
    lines.append("└─────────────────────────────────────────────────────────────┘")
    lines.append("")
    lines.append(trace.system_prompt or "(нет)")
    lines.append("")

    # User text
    lines.append("┌─────────────────────────────────────────────────────────────┐")
    lines.append("│ 👤 USER TEXT                                                │")
    lines.append("└─────────────────────────────────────────────────────────────┘")
    lines.append("")
    lines.append(trace.user_text or "(нет)")
    lines.append("")

    # Input files
    if trace.input_files:
        lines.append("┌─────────────────────────────────────────────────────────────┐")
        lines.append("│ 📁 INPUT FILES                                              │")
        lines.append("└─────────────────────────────────────────────────────────────┘")
        lines.append("")
        for i, f in enumerate(trace.input_files, 1):
            lines.append(f"  {i}. {f.get('display_name') or f.get('name', '—')}")
            lines.append(f"     mime: {f.get('mime_type', '—')}")
            lines.append(f"     uri: {f.get('uri', '—')}")
            lines.append("")

    # Thoughts (full)
    if trace.full_thoughts:
        lines.append("┌─────────────────────────────────────────────────────────────┐")
        lines.append("│ 🧠 MODEL THOUGHTS (полностью)                               │")
        lines.append("└─────────────────────────────────────────────────────────────┘")
        lines.append("")
        lines.append(trace.full_thoughts)
        lines.append("")

    # Response
    lines.append("┌─────────────────────────────────────────────────────────────┐")
    lines.append("│ 📥 RESPONSE JSON                                            │")
    lines.append("└─────────────────────────────────────────────────────────────┘")
    lines.append("")
    if trace.response_json:
        lines.append(json.dumps(trace.response_json, indent=2, ensure_ascii=False))
    else:
        lines.append("(нет ответа)")
    lines.append("")

    # Assistant text (full)
    response_text = trace.assistant_text or ""
    if not response_text and trace.response_json:
        response_text = trace.response_json.get("assistant_text", "")

    if response_text:
        lines.append("┌─────────────────────────────────────────────────────────────┐")
        lines.append("│ 💬 ASSISTANT TEXT (полностью)                               │")
        lines.append("└─────────────────────────────────────────────────────────────┘")
        lines.append("")
        lines.append(response_text)
        lines.append("")

    # Parsed actions
    if trace.parsed_actions:
        lines.append("┌─────────────────────────────────────────────────────────────┐")
        lines.append("│ ⚡ PARSED ACTIONS                                           │")
        lines.append("└─────────────────────────────────────────────────────────────┘")
        lines.append("")
        lines.append(json.dumps(trace.parsed_actions, indent=2, ensure_ascii=False))
        lines.append("")

    # Errors
    if trace.errors:
        lines.append("┌─────────────────────────────────────────────────────────────┐")
        lines.append("│ ⚠️ ERRORS                                                   │")
        lines.append("└─────────────────────────────────────────────────────────────┘")
        lines.append("")
        for err in trace.errors:
            lines.append(f"  ❌ {err}")
        lines.append("")

    lines.append("═══════════════════════════════════════════════════════════════")
    lines.append("                        КОНЕЦ ЛОГА")
    lines.append("═══════════════════════════════════════════════════════════════")

    return "\n".join(lines)


class TraceDisplayMixin:
    """Mixin for displaying trace details in inspector tabs"""

    def _display_trace_details(self, trace: ModelTrace):
        """Display trace details in all tabs"""
        from app.utils.time_utils import format_time

        time_str = format_time(trace.ts, "%Y-%m-%d %H:%M:%S")

        # === Full Log Tab ===
        full_log = build_full_log(trace, time_str)
        self.full_log_text.setPlainText(full_log)

        # === System Prompt Tab ===
        self.system_prompt_text.setPlainText(trace.system_prompt or "(нет системного промпта)")

        # === User Request Tab ===
        user_request = f"""═══════════════════════════════════════════════════════════
                        ЗАПРОС ПОЛЬЗОВАТЕЛЯ
═══════════════════════════════════════════════════════════

📅 Время: {time_str}
📌 Модель: {trace.model}
🧠 Уровень мышления: {trace.thinking_level}
📁 Файлов: {len(trace.input_files)}

───────────────────────────────────────────────────────────
                         ТЕКСТ ЗАПРОСА
───────────────────────────────────────────────────────────

{trace.user_text}

"""
        if trace.input_files:
            user_request += """───────────────────────────────────────────────────────────
                       ПРИКРЕПЛЁННЫЕ ФАЙЛЫ
───────────────────────────────────────────────────────────

"""
            for i, f in enumerate(trace.input_files, 1):
                uri = f.get("uri", "—")
                mime = f.get("mime_type", "—")
                name = f.get("display_name") or f.get("name", "—")
                user_request += f"  {i}. {name}\n     MIME: {mime}\n     URI: {uri}\n\n"

        self.user_request_text.setPlainText(user_request)

        # === Thoughts Tab ===
        if trace.full_thoughts:
            thoughts = f"""═══════════════════════════════════════════════════════════
                        МЫСЛИ МОДЕЛИ (полностью)
═══════════════════════════════════════════════════════════

⏰ Время: {time_str}
📌 Модель: {trace.model}
🧠 Уровень мышления: {trace.thinking_level}

───────────────────────────────────────────────────────────
                         ПРОЦЕСС МЫШЛЕНИЯ
───────────────────────────────────────────────────────────

{trace.full_thoughts}

───────────────────────────────────────────────────────────
                            КОНЕЦ
───────────────────────────────────────────────────────────
"""
        else:
            thoughts = f"""═══════════════════════════════════════════════════════════
                        МЫСЛИ МОДЕЛИ
═══════════════════════════════════════════════════════════

⏰ Время: {time_str}
📌 Модель: {trace.model}
🧠 Уровень мышления: {trace.thinking_level}

───────────────────────────────────────────────────────────

❌ Модель не использовала режим мышления, либо мысли не были записаны.

Возможные причины:
  • Thinking level был установлен в "low" (минимальное рассуждение)
  • Модель решила задачу без необходимости глубоких размышлений
  • Режим streaming был отключен (мысли доступны только в streaming)

───────────────────────────────────────────────────────────
"""
        self.thoughts_text.setPlainText(thoughts)

        # === Response Tab ===
        response_text = trace.assistant_text or ""
        if not response_text and trace.response_json:
            response_text = trace.response_json.get("assistant_text", "")

        # Format tokens
        tokens_info = ""
        if trace.input_tokens is not None:
            tokens_info += f"📥 Токены входа: {trace.input_tokens:,}\n"
        if trace.output_tokens is not None:
            tokens_info += f"📤 Токены выхода: {trace.output_tokens:,}\n"
        if trace.total_tokens is not None:
            tokens_info += f"📊 Всего токенов: {trace.total_tokens:,}\n"

        response = f"""═══════════════════════════════════════════════════════════
                        ОТВЕТ МОДЕЛИ (полностью)
═══════════════════════════════════════════════════════════

⏱️ Задержка: {trace.latency_ms:.2f} мс
✅ Финальный: {"Да" if trace.is_final else "Нет"}
{tokens_info}
───────────────────────────────────────────────────────────
                         ТЕКСТ ОТВЕТА
───────────────────────────────────────────────────────────

{response_text}
"""
        self.response_text.setPlainText(response)

        # === JSON Tab ===
        json_data = {
            "request": {
                "model": trace.model,
                "thinking_level": trace.thinking_level,
                "system_prompt": trace.system_prompt,
                "user_text": trace.user_text,
                "input_files": trace.input_files,
            },
            "response": trace.response_json,
            "meta": {
                "trace_id": trace.id,
                "conversation_id": str(trace.conversation_id),
                "timestamp": time_str,
                "latency_ms": trace.latency_ms,
                "is_final": trace.is_final,
            },
        }
        if trace.full_thoughts:
            json_data["thoughts"] = trace.full_thoughts
        if trace.parsed_actions:
            json_data["parsed_actions"] = trace.parsed_actions
        if trace.errors:
            json_data["errors"] = trace.errors
        if trace.input_tokens:
            json_data["meta"]["input_tokens"] = trace.input_tokens
        if trace.output_tokens:
            json_data["meta"]["output_tokens"] = trace.output_tokens
        if trace.total_tokens:
            json_data["meta"]["total_tokens"] = trace.total_tokens

        json_text = json.dumps(json_data, indent=2, ensure_ascii=False)
        self.json_text.setPlainText(json_text)

        # === Errors Tab ===
        if trace.errors:
            errors_text = "\n\n".join(trace.errors)
        else:
            errors_text = "✓ Ошибок нет"
        self.errors_text.setPlainText(errors_text)
