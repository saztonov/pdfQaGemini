"""Event handlers for MainWindow"""

import logging
from typing import TYPE_CHECKING
from uuid import UUID

from qasync import asyncSlot

# Import handler mixins
from app.ui.handlers_upload import UploadHandlersMixin
from app.ui.handlers_agentic import AgenticHandlersMixin
from app.services.context_catalog_builder import (
    build_context_catalog_for_conversation,
    context_catalog_to_json,
)

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
        from datetime import datetime

        if not self.api_client:
            self.toast_manager.error("API клиент не инициализирован")
            return

        # Build context_catalog from stored crop_index (priority) or DB fallback
        context_catalog_json = ""
        conv_id = str(self.current_conversation_id) if self.current_conversation_id else None
        stored_crops = []

        # First try: use stored crop_index from bundle upload (for existing conversation)
        if conv_id and conv_id in self._conversation_crop_indexes:
            stored_crops = self._conversation_crop_indexes[conv_id]
        # Second try: use pending crop_index (for new conversation)
        elif self._pending_crop_index:
            stored_crops = self._pending_crop_index
            logger.info(f"Using {len(stored_crops)} pending crop items")

        if stored_crops:
            # Convert crop_index to context_catalog format
            catalog = []
            for crop in stored_crops:
                item = {
                    "context_item_id": crop.get("context_item_id") or crop.get("crop_id"),
                    "kind": "crop",
                    "r2_key": crop.get("r2_key"),
                }
                if crop.get("r2_url"):
                    item["r2_url"] = crop["r2_url"]
                catalog.append(item)
            context_catalog_json = context_catalog_to_json(catalog)
            logger.info(f"Built context_catalog from stored crops: {len(catalog)} items")

        # Fallback: try to build from DB
        if not context_catalog_json and conv_id and self.supabase_repo:
            try:
                catalog, node_ids = await build_context_catalog_for_conversation(
                    self.supabase_repo,
                    conv_id,
                )
                if catalog:
                    context_catalog_json = context_catalog_to_json(catalog)
                    logger.info(
                        f"Built context_catalog from DB: {len(catalog)} items from {len(node_ids)} nodes"
                    )
            except Exception as e:
                logger.warning(f"Failed to build context_catalog from DB: {e}")

        # Save request data for tracing
        self._pending_request = {
            "ts": datetime.utcnow(),
            "user_text": user_text,
            "system_prompt": system_prompt,
            "model_name": model_name,
            "thinking_level": thinking_level,
            "file_refs": file_refs,
            "context_catalog_len": len(context_catalog_json) if context_catalog_json else 0,
        }
        logger.info(
            f"[INSPECTOR] Saved pending request: model={model_name}, user_text={user_text[:50]}..."
        )

        # Ensure conversation exists via API
        if not self.current_conversation_id:
            try:
                result = await self.api_client.create_conversation(title="Новый чат")
                conv_id_str = result.get("id")
                self.current_conversation_id = UUID(conv_id_str) if conv_id_str else None
                logger.info(f"Created conversation via API: {self.current_conversation_id}")

                # Move pending data to the new conversation
                if conv_id_str:
                    # Move pending crop_index
                    if self._pending_crop_index:
                        self._conversation_crop_indexes[conv_id_str] = self._pending_crop_index.copy()
                        logger.info(
                            f"Moved {len(self._pending_crop_index)} pending crops "
                            f"to conversation {conv_id_str}"
                        )
                        self._pending_crop_index.clear()

                    # Attach pending gemini files
                    if self._pending_gemini_file_ids and self.supabase_repo:
                        for gf_id in self._pending_gemini_file_ids:
                            try:
                                await self.supabase_repo.qa_attach_gemini_file(
                                    conversation_id=conv_id_str,
                                    gemini_file_id=gf_id,
                                )
                                logger.info(f"Attached pending file {gf_id} to {conv_id_str}")
                            except Exception as e:
                                logger.error(f"Failed to attach pending file {gf_id}: {e}")
                        self._pending_gemini_file_ids.clear()

                # Refresh chats list
                if self.chats_dock:
                    await self.chats_dock.refresh_chats()

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
                context_catalog=context_catalog_json,
            )

            job_info = result.get("job", {})
            job_id = job_info.get("id")
            logger.info(f"Message sent, job created: {job_id}")

            self.toast_manager.info("Запрос отправлен, ожидаю ответ...")

            # Use Realtime if connected, otherwise fallback to polling
            if job_id:
                if self.realtime_client and self.realtime_client.is_connected:
                    # Realtime connected - set timeout fallback in case Realtime fails
                    logger.info(f"Realtime connected, waiting for job {job_id} via Realtime")
                    self._active_job_id = job_id
                    import asyncio

                    asyncio.create_task(self._realtime_timeout_fallback(job_id, timeout=120))
                else:
                    # Realtime not connected - use polling
                    logger.info("Realtime not connected, using polling fallback")
                    await self._poll_job_status(job_id)

        except Exception as e:
            logger.error(f"Ошибка отправки сообщения: {e}", exc_info=True)
            self.toast_manager.error(f"Ошибка: {e}")
            if self.chat_panel:
                self.chat_panel.set_loading(False)
                self.chat_panel.add_system_message(f"Ошибка: {e}", "error")
                self.chat_panel.set_input_enabled(True)

    async def _poll_job_status(
        self: "MainWindow", job_id: str, max_attempts: int = 120, interval: float = 2.0
    ):
        """Poll job status until completed or failed (fallback for realtime)"""
        import asyncio
        from app.utils.time_utils import format_time
        from datetime import datetime

        logger.info(f"Starting job polling for {job_id}")

        for attempt in range(max_attempts):
            try:
                job_data = await self.api_client.get_job(job_id)
                status = job_data.get("status", "unknown")

                if status == "completed":
                    logger.info(f"Job {job_id} completed via polling")

                    # Fetch messages for conversation to get the response
                    if self.current_conversation_id:
                        messages = await self.api_client.list_messages(
                            str(self.current_conversation_id)
                        )

                        # Find the assistant message (last one with role=assistant)
                        assistant_msg = None
                        for msg in reversed(messages):
                            if msg.get("role") == "assistant":
                                assistant_msg = msg
                                break

                        if assistant_msg and self.chat_panel:
                            self.chat_panel.set_loading(False)
                            self.chat_panel.set_input_enabled(True)
                            self.chat_panel.add_message(
                                role="assistant",
                                content=assistant_msg.get("content", ""),
                                meta=assistant_msg.get("meta", {}),
                                timestamp=format_time(datetime.utcnow(), "%H:%M:%S"),
                            )
                            self.toast_manager.success("✓ Ответ получен")

                            # Create trace
                            from app.services.realtime_client import MessageUpdate

                            message_update = MessageUpdate(
                                message_id=assistant_msg.get("id", ""),
                                conversation_id=str(self.current_conversation_id),
                                role="assistant",
                                content=assistant_msg.get("content", ""),
                                meta=assistant_msg.get("meta"),
                            )
                            self._create_trace_from_response(message_update)
                    return

                elif status == "failed":
                    error_msg = job_data.get("error_message", "Неизвестная ошибка")
                    logger.error(f"Job {job_id} failed: {error_msg}")

                    if self.chat_panel:
                        self.chat_panel.set_loading(False)
                        self.chat_panel.set_input_enabled(True)
                        self.chat_panel.add_system_message(f"Ошибка: {error_msg}", "error")
                    self.toast_manager.error(f"Ошибка: {error_msg}")
                    return

                # Still processing, wait and retry
                await asyncio.sleep(interval)

            except Exception as e:
                logger.error(f"Error polling job status: {e}")
                await asyncio.sleep(interval)

        # Timeout - enable input anyway
        logger.warning(f"Job {job_id} polling timeout after {max_attempts * interval}s")
        if self.chat_panel:
            self.chat_panel.set_loading(False)
            self.chat_panel.set_input_enabled(True)
            self.chat_panel.add_system_message(
                "Таймаут ожидания ответа. Попробуйте обновить чат.", "warning"
            )
        self.toast_manager.warning("Таймаут ожидания ответа")

    async def _realtime_timeout_fallback(self: "MainWindow", job_id: str, timeout: float = 120):
        """Fallback to polling if Realtime doesn't deliver result within timeout"""
        import asyncio

        await asyncio.sleep(timeout)

        # Check if job is still active (not completed via Realtime)
        if getattr(self, "_active_job_id", None) == job_id:
            logger.warning(f"Realtime timeout for job {job_id}, falling back to polling")
            self._active_job_id = None
            await self._poll_job_status(job_id, max_attempts=30, interval=2.0)
