"""Chat management for main window"""

import logging
from uuid import UUID
from qasync import asyncSlot

logger = logging.getLogger(__name__)


class ChatManagementMixin:
    """Mixin for chat conversation management"""

    async def _ensure_conversation(self):
        """Ensure conversation exists"""
        if not self.current_conversation_id and self.supabase_repo:
            try:
                from datetime import datetime
                from app.utils.time_utils import format_time

                timestamp = format_time(datetime.utcnow(), "%d.%m.%y %H:%M")
                conv = await self.supabase_repo.qa_create_conversation(
                    client_id=self.client_id,
                    title=f"Чат {timestamp}",
                )
                self.current_conversation_id = conv.id

                # Refresh chats list
                if self.chats_dock:
                    await self.chats_dock.refresh_chats()

                self.toast_manager.info("New chat created")
            except Exception as e:
                logger.error(f"Ошибка создания разговора: {e}", exc_info=True)
                self.toast_manager.error(f"Ошибка создания разговора: {e}")

    @asyncSlot(str)
    async def _on_chat_selected(self, conversation_id: str):
        """Handle chat selection"""
        logger.info(f"Переключение на чат: {conversation_id}")

        if not self.supabase_repo:
            self.toast_manager.error("Репозиторий не инициализирован")
            return

        try:
            # Update current conversation
            self.current_conversation_id = UUID(conversation_id)

            # Load chat messages
            messages = await self.supabase_repo.qa_list_messages(conversation_id)

            # Convert to chat panel format
            from app.utils.time_utils import format_time

            chat_messages = []
            for msg in messages:
                chat_messages.append(
                    {
                        "role": msg.role,
                        "content": msg.content,
                        "meta": msg.meta,
                        "timestamp": (
                            format_time(msg.created_at, "%H:%M:%S") if msg.created_at else ""
                        ),
                    }
                )

            # Load history to chat panel
            if self.chat_panel:
                self.chat_panel.load_history(chat_messages)

            # Sync files to chat (files already loaded in ChatListItem)
            self._sync_files_to_chat()

            logger.info(f"Chat loaded: {len(messages)} messages")

        except Exception as e:
            logger.error(f"Ошибка переключения чата: {e}", exc_info=True)
            self.toast_manager.error(f"Ошибка: {e}")

    @asyncSlot(str, str)
    async def _on_chat_created(self, conversation_id: str, title: str):
        """Handle chat creation"""
        logger.info(f"Создан новый чат: {conversation_id} - {title}")

        # Switch to new chat
        await self._on_chat_selected(conversation_id)

    @asyncSlot(str)
    async def _on_chat_deleted(self, conversation_id: str):
        """Handle chat deletion"""
        logger.info(f"Удален чат: {conversation_id}")

        # If empty string - all chats deleted
        if not conversation_id:
            logger.info("Удалены все чаты")
            self.current_conversation_id = None

            # Clear chat panel
            if self.chat_panel:
                self.chat_panel.clear_chat()

            # Don't create new conversation automatically
            return

        # If current chat was deleted, clear it
        if self.current_conversation_id and str(self.current_conversation_id) == conversation_id:
            self.current_conversation_id = None

            # Clear chat panel
            if self.chat_panel:
                self.chat_panel.clear_chat()

            # Don't create new conversation automatically
            # It will be created on first message
