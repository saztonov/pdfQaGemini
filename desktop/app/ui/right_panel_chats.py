"""Chats tab mixin for RightContextPanel"""
import asyncio
import logging
from PySide6.QtWidgets import QInputDialog, QMessageBox
from qasync import asyncSlot

logger = logging.getLogger(__name__)


class RightPanelChatsMixin:
    """Mixin with chats tab methods for RightContextPanel"""

    async def refresh_chats(self):
        """Refresh chats list with expandable items"""
        if not self.supabase_repo:
            if self.toast_manager:
                self.toast_manager.error("Репозиторий не инициализирован")
            return

        try:
            from app.ui.chat_list_item import ChatListItem

            conversations = await self.supabase_repo.qa_list_conversations(client_id=self.client_id)
            self._conversations = conversations

            # Get all Gemini files
            if self.server_mode and self.api_client:
                all_files_raw = await self.api_client.list_gemini_files()
                all_files = [
                    {
                        "name": f.get("gemini_name"),
                        "uri": f.get("gemini_uri"),
                        "display_name": f.get("display_name"),
                        "mime_type": f.get("mime_type"),
                        "size_bytes": f.get("size_bytes"),
                        "token_count": f.get("token_count"),
                        "expiration_time": f.get("expiration_time"),
                    }
                    for f in all_files_raw
                ]
            elif self.gemini_client:
                all_files = await self.gemini_client.list_files()
            else:
                all_files = []

            # Clear existing items (keep stretch at end)
            while self.chats_layout.count() > 1:
                item = self.chats_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            self._chat_items.clear()

            # Create chat items
            for conv in conversations:
                conv_id = str(conv.id)
                conv_data = {
                    "id": conv.id,
                    "title": conv.title,
                    "message_count": conv.message_count,
                    "file_count": conv.file_count,
                    "created_at": conv.created_at,
                    "updated_at": conv.updated_at,
                    "last_message_at": conv.last_message_at,
                }

                chat_item = ChatListItem(conv_data)
                chat_item.clicked.connect(self._on_chat_item_clicked)
                chat_item.doubleClicked.connect(self._on_chat_item_double_clicked)
                chat_item.fileAddClicked.connect(self._on_file_add_clicked)
                chat_item.fileDeleteClicked.connect(self._on_file_delete_clicked)

                # Load files for this conversation
                try:
                    conv_files = await self.supabase_repo.qa_get_conversation_files(conv_id)
                    db_files_map = {f.get("gemini_name"): f for f in conv_files if f.get("gemini_name")}

                    # Merge files data
                    merged_files = []
                    for f in all_files:
                        name = f.get("name")
                        if name in db_files_map:
                            db_file = db_files_map[name]
                            merged_files.append({
                                "name": name,
                                "uri": f.get("uri"),
                                "display_name": db_file.get("display_name") or f.get("display_name"),
                                "mime_type": db_file.get("mime_type") or f.get("mime_type"),
                                "size_bytes": db_file.get("size_bytes") or f.get("size_bytes"),
                                "token_count": db_file.get("token_count") or f.get("token_count"),
                                "expiration_time": f.get("expiration_time"),
                            })

                    chat_item.set_files(merged_files)
                except Exception as e:
                    logger.warning(f"Не удалось загрузить файлы для чата {conv_id}: {e}")

                # Restore selection state
                if conv_id == self.conversation_id:
                    chat_item.set_selected(True)
                    chat_item.expand()
                    # Update gemini_files for current conversation
                    self.gemini_files = merged_files

                self._chat_items[conv_id] = chat_item
                self.chats_layout.insertWidget(self.chats_layout.count() - 1, chat_item)

            self.chats_footer_label.setText(f"Чатов: {len(conversations)}")

        except Exception as e:
            logger.error(f"Ошибка загрузки чатов: {e}", exc_info=True)
            if self.toast_manager:
                self.toast_manager.error(f"Ошибка: {e}")

    @asyncSlot()
    async def _on_new_chat_clicked(self):
        """Handle new chat button"""
        if not self.supabase_repo:
            if self.toast_manager:
                self.toast_manager.error("Репозиторий не инициализирован")
            return

        # Generate default title with timestamp
        from datetime import datetime
        from app.utils.time_utils import format_time

        default_title = f"Чат {format_time(datetime.utcnow(), '%d.%m.%y %H:%M')}"

        # Ask for chat title
        title, ok = QInputDialog.getText(
            self, "Новый чат", "Введите название чата:", text=default_title
        )

        if ok and title:
            try:
                conv = await self.supabase_repo.qa_create_conversation(
                    client_id=self.client_id, title=title
                )
                await self.refresh_chats()

                if self.toast_manager:
                    self.toast_manager.success(f"Чат '{title}' создан")

                self.chatCreated.emit(str(conv.id), title)

            except Exception as e:
                logger.error(f"Ошибка создания чата: {e}", exc_info=True)
                if self.toast_manager:
                    self.toast_manager.error(f"Ошибка: {e}")

    @asyncSlot()
    async def _on_delete_chat_clicked(self):
        """Handle delete chat button"""
        if not self.supabase_repo:
            if self.toast_manager:
                self.toast_manager.error("Репозиторий не инициализирован")
            return

        if not self.conversation_id:
            if self.toast_manager:
                self.toast_manager.warning("Выберите чат для удаления")
            return

        # Confirm deletion
        reply = QMessageBox.question(
            self,
            "Удаление чата",
            "Вы уверены, что хотите удалить этот чат?\nВсе сообщения и привязанные файлы будут удалены.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            try:
                conversation_id = self.conversation_id
                await self.supabase_repo.qa_delete_conversation(conversation_id)

                # Delete chat folder from R2
                if self.r2_client:
                    try:
                        await self.r2_client.delete_chat_folder(conversation_id)
                    except Exception as e:
                        logger.warning(f"Не удалось удалить папку чата из R2: {e}")

                self.conversation_id = None
                await self.refresh_chats()

                if self.toast_manager:
                    self.toast_manager.success("Чат удален")

                self.chatDeleted.emit(conversation_id)
                self.btn_delete_chat.setEnabled(False)

            except Exception as e:
                logger.error(f"Ошибка удаления чата: {e}", exc_info=True)
                if self.toast_manager:
                    self.toast_manager.error(f"Ошибка: {e}")

    def _on_chat_double_clicked_by_id(self, conversation_id: str):
        """Handle chat double click for renaming"""
        if not conversation_id:
            return

        # Get current title
        current_title = "Новый чат"
        if conversation_id in self._chat_items:
            current_title = self._chat_items[conversation_id].conversation_data.get("title", "Новый чат")

        # Ask for new title
        new_title, ok = QInputDialog.getText(
            self, "Переименовать чат", "Введите новое название чата:", text=current_title
        )

        if ok and new_title and new_title != current_title:
            asyncio.create_task(self._rename_chat(conversation_id, new_title))

    async def _rename_chat(self, conversation_id: str, new_title: str):
        """Rename chat in database"""
        if not self.supabase_repo:
            if self.toast_manager:
                self.toast_manager.error("Репозиторий не инициализирован")
            return

        try:
            await self.supabase_repo.qa_update_conversation(
                conversation_id=conversation_id, title=new_title
            )

            await self.refresh_chats()

            if self.toast_manager:
                self.toast_manager.success(f"Чат переименован: {new_title}")

        except Exception as e:
            logger.error(f"Ошибка переименования чата: {e}", exc_info=True)
            if self.toast_manager:
                self.toast_manager.error(f"Ошибка: {e}")

    @asyncSlot()
    async def _on_delete_all_chats_clicked(self):
        """Handle delete all chats button"""
        if not self.supabase_repo:
            if self.toast_manager:
                self.toast_manager.error("Репозиторий не инициализирован")
            return

        # Get chats count
        chat_count = len(self._chat_items)

        if chat_count == 0:
            if self.toast_manager:
                self.toast_manager.info("Нет чатов для удаления")
            return

        # Confirm deletion
        reply = QMessageBox.question(
            self,
            "Удаление всех чатов",
            f"Вы уверены, что хотите удалить ВСЕ чаты ({chat_count} шт.)?\n\n"
            "Будут удалены:\n"
            "- Все сообщения\n"
            "- Все связи с файлами\n"
            "- Все данные на R2\n\n"
            "Это действие необратимо!",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            try:
                if self.toast_manager:
                    self.toast_manager.info(f"Удаление {chat_count} чатов...")

                # Get all conversation IDs
                conversation_ids = list(self._chat_items.keys())

                # Delete all conversations
                await self.supabase_repo.qa_delete_all_conversations(client_id=self.client_id)

                # Delete all chat folders from R2
                if self.r2_client:
                    try:
                        for conv_id in conversation_ids:
                            await self.r2_client.delete_chat_folder(conv_id)
                        logger.info(f"Удалены папки {len(conversation_ids)} чатов из R2")
                    except Exception as e:
                        logger.warning(f"Не удалось удалить папки чатов из R2: {e}")

                self.conversation_id = None
                await self.refresh_chats()

                self.chatDeleted.emit("")  # Empty string means all deleted
                self.btn_delete_chat.setEnabled(False)

                if self.toast_manager:
                    self.toast_manager.success(f"Удалено {len(conversation_ids)} чатов")

            except Exception as e:
                logger.error(f"Ошибка удаления всех чатов: {e}", exc_info=True)
                if self.toast_manager:
                    self.toast_manager.error(f"Ошибка: {e}")
