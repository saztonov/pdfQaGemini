"""Files management mixin for RightContextPanel"""

import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class RightPanelFilesMixin:
    """Mixin with files management methods for RightContextPanel"""

    async def refresh_files(self, conversation_id: Optional[str] = None):
        """Refresh files for a specific conversation (updates chat items)"""
        # Now delegates to refresh_chats which handles everything
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

    # Legacy compatibility methods
    @property
    def context_items(self):
        return []

    def set_context_node_ids(self, node_ids: list[str]):
        pass

    async def load_node_files(self):
        pass

    async def add_files_to_context(self, files_info: list[dict]):
        pass

    async def load_context_from_db(self):
        await self.refresh_chats()

    def update_context_item_status(self, item_id: str, status: str, gemini_name: str = None):
        pass

    def _toggle_files_section(self):
        """Legacy - no longer needed"""
        pass

    def _on_files_table_selection_changed(self):
        """Legacy - no longer needed"""
        pass

    async def _on_refresh_files_clicked(self):
        """Legacy - no longer needed"""
        pass

    async def _on_delete_files_clicked(self):
        """Legacy - no longer needed"""
        pass

    def _on_cell_changed(self, row: int, col: int):
        """Legacy - no longer needed"""
        pass

    def _update_table(self):
        """Legacy - no longer needed"""
        pass

    def _update_files_count(self):
        """Legacy - no longer needed"""
        pass

    async def delete_selected_files(self):
        """Legacy - no longer needed"""
        pass

    async def reload_selected_files(self):
        """Legacy - no longer needed"""
        pass

    async def _get_file_metadata(self, gemini_name: str) -> Optional[dict]:
        """Get file metadata from database"""
        if not self.supabase_repo:
            return None

        try:

            def _sync_get():
                client = self.supabase_repo._get_client()
                response = (
                    client.table("qa_gemini_files")
                    .select("*")
                    .eq("gemini_name", gemini_name)
                    .limit(1)
                    .execute()
                )
                if response.data:
                    return response.data[0]
                return None

            return await asyncio.to_thread(_sync_get)
        except Exception as e:
            logger.error(f"Ошибка получения метаданных: {e}", exc_info=True)
            return None
