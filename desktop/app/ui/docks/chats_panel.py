"""Standalone Chats panel extracted from RightContextPanel"""

import asyncio
import logging
from typing import Optional

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QScrollArea,
    QFrame,
    QInputDialog,
    QMessageBox,
)
from PySide6.QtCore import Signal, Qt
from qasync import asyncSlot

from app.services.gemini_client import GeminiClient
from app.ui.chat_list_item import ChatListItem

logger = logging.getLogger(__name__)


class ChatsPanel(QWidget):
    """Standalone panel for Chats list and Gemini files management"""

    # Signals
    chatSelected = Signal(str)  # conversation_id
    chatCreated = Signal(str, str)  # conversation_id, title
    chatDeleted = Signal(str)  # conversation_id
    filesSelectionChanged = Signal(list)  # list[dict] selected files
    filesListChanged = Signal()  # emitted when files list changes

    def __init__(
        self,
        supabase_repo=None,
        gemini_client: Optional[GeminiClient] = None,
        r2_client=None,
        toast_manager=None,
        parent=None,
    ):
        super().__init__(parent)
        self.supabase_repo = supabase_repo
        self.gemini_client = gemini_client
        self.r2_client = r2_client
        self.toast_manager = toast_manager

        # State
        self.client_id: str = "default"
        self.conversation_id: Optional[str] = None
        self.gemini_files: list[dict] = []
        self._selected_for_request: set[str] = set()
        self.api_client = None
        self.server_mode: bool = False
        self._chat_items: dict[str, ChatListItem] = {}
        self._conversations: list = []

        self._setup_ui()

    def _setup_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QWidget()
        header.setStyleSheet("background-color: #252526; border-bottom: 1px solid #3e3e42;")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(10, 10, 10, 10)
        header_layout.setSpacing(8)

        header_label = QLabel("CHATS")
        header_label.setStyleSheet("color: #bbbbbb; font-weight: bold; font-size: 9pt;")
        header_layout.addWidget(header_label)

        # Toolbar
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setSpacing(8)

        self.btn_new_chat = QPushButton("+ New chat")
        self.btn_new_chat.setCursor(Qt.PointingHandCursor)
        self.btn_new_chat.setStyleSheet(self._button_style())
        self.btn_new_chat.clicked.connect(self._on_new_chat_clicked)
        toolbar_layout.addWidget(self.btn_new_chat)

        self.btn_delete_chat = QPushButton("Delete")
        self.btn_delete_chat.setCursor(Qt.PointingHandCursor)
        self.btn_delete_chat.setEnabled(False)
        self.btn_delete_chat.setStyleSheet(self._button_style())
        self.btn_delete_chat.clicked.connect(self._on_delete_chat_clicked)
        toolbar_layout.addWidget(self.btn_delete_chat)

        toolbar_layout.addStretch()

        self.btn_delete_all_chats = QPushButton("Delete All")
        self.btn_delete_all_chats.setCursor(Qt.PointingHandCursor)
        self.btn_delete_all_chats.setStyleSheet(self._delete_all_button_style())
        self.btn_delete_all_chats.setToolTip("Delete all chats")
        self.btn_delete_all_chats.clicked.connect(self._on_delete_all_chats_clicked)
        toolbar_layout.addWidget(self.btn_delete_all_chats)

        header_layout.addLayout(toolbar_layout)
        layout.addWidget(header)

        # Scrollable chats list
        self.chats_scroll = QScrollArea()
        self.chats_scroll.setWidgetResizable(True)
        self.chats_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.chats_scroll.setStyleSheet(
            """
            QScrollArea {
                background-color: #1e1e1e;
                border: none;
            }
            QScrollBar:vertical {
                background-color: #1e1e1e;
                width: 8px;
            }
            QScrollBar::handle:vertical {
                background-color: #3e3e42;
                border-radius: 4px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #505050;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """
        )

        self.chats_container = QFrame()
        self.chats_container.setStyleSheet("background-color: #1e1e1e;")
        self.chats_layout = QVBoxLayout(self.chats_container)
        self.chats_layout.setContentsMargins(0, 0, 0, 0)
        self.chats_layout.setSpacing(0)
        self.chats_layout.addStretch()

        self.chats_scroll.setWidget(self.chats_container)
        layout.addWidget(self.chats_scroll, 1)

        # Footer
        self.chats_footer_label = QLabel("Chats: 0")
        self.chats_footer_label.setStyleSheet("color: #666; font-size: 8pt; padding: 4px 10px;")
        layout.addWidget(self.chats_footer_label)

    def set_services(
        self,
        supabase_repo,
        gemini_client: GeminiClient,
        r2_client,
        toast_manager,
        client_id: str = "default",
        api_client=None,
        server_mode: bool = False,
    ):
        """Set service dependencies"""
        self.supabase_repo = supabase_repo
        self.gemini_client = gemini_client
        self.r2_client = r2_client
        self.toast_manager = toast_manager
        self.client_id = client_id
        self.api_client = api_client
        self.server_mode = server_mode

    # Style methods
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

    # Chat item event handlers
    def _on_chat_item_clicked(self, conversation_id: str):
        """Handle chat item click"""
        # Deselect and collapse all items
        for conv_id, item in self._chat_items.items():
            item.set_selected(False)
            if conv_id != conversation_id:
                item.collapse()

        # Select clicked item and expand
        if conversation_id in self._chat_items:
            chat_item = self._chat_items[conversation_id]
            chat_item.set_selected(True)
            chat_item.expand()
            self.gemini_files = chat_item._files

        self.conversation_id = conversation_id
        self.btn_delete_chat.setEnabled(True)
        self.chatSelected.emit(conversation_id)

    def _on_chat_item_double_clicked(self, conversation_id: str):
        """Handle chat item double click for renaming"""
        self._on_chat_double_clicked_by_id(conversation_id)

    def _on_file_delete_clicked(self, conversation_id: str, gemini_name: str):
        """Handle file delete button click"""
        asyncio.create_task(self._delete_file_by_name(gemini_name))

    async def _delete_file_by_name(self, gemini_name: str):
        """Delete single file by name"""
        if self.server_mode:
            if not self.api_client:
                return
        else:
            if not self.gemini_client:
                return

        try:
            if self.server_mode:
                await self.api_client.delete_file(gemini_name)
            else:
                await self.gemini_client.delete_file(gemini_name)

            self._selected_for_request.discard(gemini_name)

            if self.supabase_repo:
                try:
                    await self.supabase_repo.qa_delete_gemini_file_by_name(gemini_name)
                except Exception as e:
                    logger.warning(f"Failed to delete file metadata: {e}")

            await self.refresh_chats()
            self.filesListChanged.emit()

            if self.toast_manager:
                self.toast_manager.success("File deleted")

        except Exception as e:
            logger.error(f"Error deleting file: {e}", exc_info=True)
            if self.toast_manager:
                self.toast_manager.error(f"Error: {e}")

    # Chats management methods (from RightPanelChatsMixin)
    async def refresh_chats(self):
        """Refresh chats list with expandable items"""
        if not self.supabase_repo:
            if self.toast_manager:
                self.toast_manager.error("Repository not initialized")
            return

        try:
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
                chat_item.fileDeleteClicked.connect(self._on_file_delete_clicked)

                # Load files for this conversation
                try:
                    conv_files = await self.supabase_repo.qa_get_conversation_files(conv_id)
                    db_files_map = {
                        f.get("gemini_name"): f for f in conv_files if f.get("gemini_name")
                    }

                    # Merge files data
                    merged_files = []
                    for f in all_files:
                        name = f.get("name")
                        if name in db_files_map:
                            db_file = db_files_map[name]
                            merged_files.append(
                                {
                                    "name": name,
                                    "uri": f.get("uri"),
                                    "display_name": db_file.get("display_name")
                                    or f.get("display_name"),
                                    "mime_type": db_file.get("mime_type") or f.get("mime_type"),
                                    "size_bytes": db_file.get("size_bytes") or f.get("size_bytes"),
                                    "token_count": db_file.get("token_count")
                                    or f.get("token_count"),
                                    "expiration_time": f.get("expiration_time"),
                                }
                            )

                    chat_item.set_files(merged_files)
                except Exception as e:
                    logger.warning(f"Failed to load files for chat {conv_id}: {e}")
                    merged_files = []

                # Restore selection state
                if conv_id == self.conversation_id:
                    chat_item.set_selected(True)
                    chat_item.expand()
                    self.gemini_files = merged_files

                self._chat_items[conv_id] = chat_item
                self.chats_layout.insertWidget(self.chats_layout.count() - 1, chat_item)

            self.chats_footer_label.setText(f"Chats: {len(conversations)}")

        except Exception as e:
            logger.error(f"Error loading chats: {e}", exc_info=True)
            if self.toast_manager:
                self.toast_manager.error(f"Error: {e}")

    @asyncSlot()
    async def _on_new_chat_clicked(self):
        """Handle new chat button"""
        if not self.supabase_repo:
            if self.toast_manager:
                self.toast_manager.error("Repository not initialized")
            return

        from datetime import datetime
        from app.utils.time_utils import format_time

        default_title = f"Chat {format_time(datetime.utcnow(), '%d.%m.%y %H:%M')}"

        title, ok = QInputDialog.getText(
            self, "New chat", "Enter chat name:", text=default_title
        )

        if ok and title:
            try:
                conv = await self.supabase_repo.qa_create_conversation(
                    client_id=self.client_id, title=title
                )
                await self.refresh_chats()

                if self.toast_manager:
                    self.toast_manager.success(f"Chat '{title}' created")

                self.chatCreated.emit(str(conv.id), title)

            except Exception as e:
                logger.error(f"Error creating chat: {e}", exc_info=True)
                if self.toast_manager:
                    self.toast_manager.error(f"Error: {e}")

    @asyncSlot()
    async def _on_delete_chat_clicked(self):
        """Handle delete chat button"""
        if not self.supabase_repo:
            if self.toast_manager:
                self.toast_manager.error("Repository not initialized")
            return

        if not self.conversation_id:
            if self.toast_manager:
                self.toast_manager.warning("Select a chat to delete")
            return

        reply = QMessageBox.question(
            self,
            "Delete chat",
            "Are you sure you want to delete this chat?\nAll messages and linked files will be deleted.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            try:
                conversation_id = self.conversation_id
                await self.supabase_repo.qa_delete_conversation(conversation_id)

                if self.r2_client:
                    try:
                        await self.r2_client.delete_chat_folder(conversation_id)
                    except Exception as e:
                        logger.warning(f"Failed to delete chat folder from R2: {e}")

                self.conversation_id = None
                await self.refresh_chats()

                if self.toast_manager:
                    self.toast_manager.success("Chat deleted")

                self.chatDeleted.emit(conversation_id)
                self.btn_delete_chat.setEnabled(False)

            except Exception as e:
                logger.error(f"Error deleting chat: {e}", exc_info=True)
                if self.toast_manager:
                    self.toast_manager.error(f"Error: {e}")

    def _on_chat_double_clicked_by_id(self, conversation_id: str):
        """Handle chat double click for renaming"""
        if not conversation_id:
            return

        current_title = "New chat"
        if conversation_id in self._chat_items:
            current_title = self._chat_items[conversation_id].conversation_data.get(
                "title", "New chat"
            )

        new_title, ok = QInputDialog.getText(
            self, "Rename chat", "Enter new chat name:", text=current_title
        )

        if ok and new_title and new_title != current_title:
            asyncio.create_task(self._rename_chat(conversation_id, new_title))

    async def _rename_chat(self, conversation_id: str, new_title: str):
        """Rename chat in database"""
        if not self.supabase_repo:
            if self.toast_manager:
                self.toast_manager.error("Repository not initialized")
            return

        try:
            await self.supabase_repo.qa_update_conversation(
                conversation_id=conversation_id, title=new_title
            )

            await self.refresh_chats()

            if self.toast_manager:
                self.toast_manager.success(f"Chat renamed: {new_title}")

        except Exception as e:
            logger.error(f"Error renaming chat: {e}", exc_info=True)
            if self.toast_manager:
                self.toast_manager.error(f"Error: {e}")

    @asyncSlot()
    async def _on_delete_all_chats_clicked(self):
        """Handle delete all chats button"""
        if not self.supabase_repo:
            if self.toast_manager:
                self.toast_manager.error("Repository not initialized")
            return

        chat_count = len(self._chat_items)

        if chat_count == 0:
            if self.toast_manager:
                self.toast_manager.info("No chats to delete")
            return

        reply = QMessageBox.question(
            self,
            "Delete all chats",
            f"Are you sure you want to delete ALL chats ({chat_count})?\n\n"
            "The following will be deleted:\n"
            "- All messages\n"
            "- All file links\n"
            "- All R2 data\n\n"
            "This action is irreversible!",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            try:
                if self.toast_manager:
                    self.toast_manager.info(f"Deleting {chat_count} chats...")

                conversation_ids = list(self._chat_items.keys())

                await self.supabase_repo.qa_delete_all_conversations(client_id=self.client_id)

                if self.r2_client:
                    try:
                        for conv_id in conversation_ids:
                            await self.r2_client.delete_chat_folder(conv_id)
                        logger.info(f"Deleted {len(conversation_ids)} chat folders from R2")
                    except Exception as e:
                        logger.warning(f"Failed to delete chat folders from R2: {e}")

                self.conversation_id = None
                await self.refresh_chats()

                self.chatDeleted.emit("")
                self.btn_delete_chat.setEnabled(False)

                if self.toast_manager:
                    self.toast_manager.success(f"Deleted {len(conversation_ids)} chats")

            except Exception as e:
                logger.error(f"Error deleting all chats: {e}", exc_info=True)
                if self.toast_manager:
                    self.toast_manager.error(f"Error: {e}")

    # Files management methods (from RightPanelFilesMixin)
    async def refresh_files(self, conversation_id: Optional[str] = None):
        """Refresh files for a specific conversation"""
        if conversation_id:
            self.conversation_id = conversation_id
        await self.refresh_chats()

    def get_selected_files_for_request(self) -> list[dict]:
        """Get files selected for request"""
        selected = []
        for conv_id, item in self._chat_items.items():
            for f in item._files:
                name = f.get("name", "")
                if name in self._selected_for_request:
                    selected.append(
                        {
                            "name": name,
                            "uri": f.get("uri"),
                            "mime_type": f.get("mime_type"),
                            "display_name": f.get("display_name"),
                        }
                    )
        return selected

    def select_file_for_request(self, file_name: str):
        """Select specific file for request"""
        self._selected_for_request.add(file_name)
        self.filesSelectionChanged.emit(self.get_selected_files_for_request())

    def clear_file_selection(self):
        """Clear all file selections"""
        self._selected_for_request.clear()
        self.filesSelectionChanged.emit([])

    # Legacy compatibility property
    @property
    def context_items(self):
        """Legacy compatibility - returns empty list"""
        return []
