"""Event handlers for MainWindow"""
import logging
from typing import TYPE_CHECKING
from uuid import UUID

from qasync import asyncSlot

# Import handler mixins
from app.ui.handlers_upload import UploadHandlersMixin
from app.ui.handlers_agentic import AgenticHandlersMixin

if TYPE_CHECKING:
    from app.ui.main_window import MainWindow

logger = logging.getLogger(__name__)


class MainWindowHandlers(UploadHandlersMixin, AgenticHandlersMixin):
    """Mixin for MainWindow event handlers"""

    @asyncSlot(list)
    async def _on_upload_context_items(self: "MainWindow", item_ids: list):
        """Legacy handler - no longer used"""
        pass

    @asyncSlot(str, str, str, str, str, object, list)
    async def _on_ask_model(
        self: "MainWindow",
        user_text: str,
        system_prompt: str,
        user_text_template: str,
        model_name: str,
        thinking_level: str,
        thinking_budget: int,
        file_refs: list,
    ):
        """Handle ask model request - server mode or local agentic mode"""
        logger.info("=== _on_ask_model ===")
        logger.info(f"  user_text: {user_text[:50]}...")
        logger.info(
            f"  user_text_template: {user_text_template[:50]}..."
            if user_text_template
            else "  user_text_template: (none)"
        )
        logger.info(f"  model_name: {model_name}, thinking: {thinking_level}")
        logger.info(f"  file_refs: {len(file_refs)}")
        logger.info(f"  server_mode: {self.server_mode}")

        if not user_text.strip():
            self.toast_manager.warning("Пустое сообщение")
            return

        # Server mode - use API client
        if self.server_mode:
            await self._on_ask_model_server(
                user_text=user_text,
                system_prompt=system_prompt,
                user_text_template=user_text_template,
                model_name=model_name,
                thinking_level=thinking_level,
                thinking_budget=thinking_budget,
                file_refs=file_refs,
            )
            return

        # Local mode - use agent directly
        if not self.agent:
            self.toast_manager.error("Агент не инициализирован. Нажмите 'Подключиться'.")
            return

        # Ensure conversation exists
        if not self.current_conversation_id:
            await self._ensure_conversation()
            if not self.current_conversation_id:
                self.toast_manager.error("Не удалось создать разговор")
                return

        if self.chat_panel:
            self.chat_panel.set_input_enabled(False)
            self.chat_panel.add_user_message(user_text, file_refs)

        try:
            await self._run_agentic(
                question=user_text,
                system_prompt=system_prompt,
                user_text_template=user_text_template,
                model_name=model_name,
                thinking_level=thinking_level,
                thinking_budget=thinking_budget,
                initial_file_refs=file_refs,
            )
        except Exception as e:
            logger.error(f"Ошибка agentic loop: {e}", exc_info=True)
            self.toast_manager.error(f"Ошибка: {e}")
            if self.chat_panel:
                self.chat_panel.add_system_message(f"Ошибка: {e}", "error")
        finally:
            if self.chat_panel:
                self.chat_panel.set_input_enabled(True)

    async def _on_ask_model_server(
        self: "MainWindow",
        user_text: str,
        system_prompt: str,
        user_text_template: str,
        model_name: str,
        thinking_level: str,
        thinking_budget: int,
        file_refs: list,
    ):
        """Handle ask model in server mode - send via API and wait for Realtime update"""
        if not self.api_client:
            self.toast_manager.error("API клиент не инициализирован")
            return

        # Ensure conversation exists via API
        if not self.current_conversation_id:
            try:
                result = await self.api_client.create_conversation(title="Новый чат")
                conv_id_str = result.get("id")
                self.current_conversation_id = UUID(conv_id_str) if conv_id_str else None
                logger.info(f"Created conversation via API: {self.current_conversation_id}")

                # Refresh chats list
                if self.right_panel:
                    await self.right_panel.refresh_chats()

            except Exception as e:
                logger.error(f"Failed to create conversation: {e}", exc_info=True)
                self.toast_manager.error(f"Ошибка создания разговора: {e}")
                return

        # Subscribe to current conversation for realtime updates
        if self.realtime_client:
            self.realtime_client.subscribe_to_conversation(str(self.current_conversation_id))

        # Show user message in chat
        if self.chat_panel:
            self.chat_panel.set_input_enabled(False)
            self.chat_panel.add_user_message(user_text, file_refs)
            self.chat_panel.set_loading(True)

        try:
            # Send message via API (creates job on server)
            result = await self.api_client.send_message(
                conversation_id=str(self.current_conversation_id),
                user_text=user_text,
                system_prompt=system_prompt,
                user_text_template=user_text_template,
                model_name=model_name,
                thinking_level=thinking_level,
                thinking_budget=thinking_budget,
                file_refs=file_refs,
            )

            job_info = result.get("job", {})
            job_id = job_info.get("id")
            logger.info(f"Message sent, job created: {job_id}")

            self.toast_manager.info("Запрос отправлен, ожидаю ответ...")

            # Response will arrive via Realtime subscription
            # The _on_job_updated and _on_realtime_message handlers in main_window.py
            # will process the response when it arrives

        except Exception as e:
            logger.error(f"Ошибка отправки сообщения: {e}", exc_info=True)
            self.toast_manager.error(f"Ошибка: {e}")
            if self.chat_panel:
                self.chat_panel.set_loading(False)
                self.chat_panel.add_system_message(f"Ошибка: {e}", "error")
                self.chat_panel.set_input_enabled(True)
