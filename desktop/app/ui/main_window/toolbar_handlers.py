"""Toolbar and panel handlers for main window"""

import logging
from qasync import asyncSlot

logger = logging.getLogger(__name__)


class ToolbarHandlersMixin:
    """Mixin for toolbar and panel visibility handlers"""

    def _enable_actions(self):
        """Enable actions after connect"""
        self.action_refresh_tree.setEnabled(True)
        self.action_upload.setEnabled(True)
        self.action_refresh_gemini.setEnabled(True)
        self.action_prompts.setEnabled(True)

    @asyncSlot()
    async def _on_refresh_tree(self):
        """Refresh projects tree"""
        self.toast_manager.info("Refreshing tree...")
        if self.projects_dock:
            await self.projects_dock.load_roots(client_id=self.client_id)
            self.toast_manager.success("Tree refreshed")

    @asyncSlot()
    async def _on_upload_selected(self):
        """Upload selected items from tree to Gemini"""
        if self.projects_dock:
            await self.projects_dock.add_selected_to_context()

    @asyncSlot()
    async def _on_refresh_gemini(self):
        """Refresh Gemini Files list"""
        if self.chats_dock:
            conv_id = str(self.current_conversation_id) if self.current_conversation_id else None
            await self.chats_dock.refresh_files(conversation_id=conv_id)
            self._sync_files_to_chat()
            await self.chats_dock.refresh_chats()

    @asyncSlot()
    async def _on_refresh_gemini_async(self):
        """Async refresh Gemini files"""
        if self.chats_dock:
            await self.chats_dock.refresh_files()
            self._sync_files_to_chat()

    def _on_open_inspector(self):
        """Open Model Inspector window"""
        from app.ui.model_inspector import ModelInspectorWindow

        if not self.inspector_window:
            self.inspector_window = ModelInspectorWindow(self.trace_store, self)

        self.inspector_window.show()
        self.inspector_window.raise_()
        self.inspector_window.activateWindow()

    async def _load_gemini_models(self):
        """Load available Gemini models"""
        from app.models.schemas import AVAILABLE_MODELS

        try:
            # In server mode gemini_client is None, use AVAILABLE_MODELS directly
            if self.gemini_client:
                models = await self.gemini_client.list_models()
            else:
                models = AVAILABLE_MODELS.copy()

            if self.chat_panel and models:
                self.chat_panel.set_models(models)
                logger.info(f"Загружено {len(models)} моделей")

        except Exception as e:
            logger.error(f"Ошибка загрузки моделей: {e}", exc_info=True)
            self.toast_manager.error(f"Ошибка: {e}")

    async def _load_prompts(self):
        """Load user prompts"""
        if not self.supabase_repo:
            return

        try:
            prompts = await self.supabase_repo.prompts_list(client_id=self.client_id)

            if self.chat_panel:
                self.chat_panel.set_prompts(prompts)
                logger.info(f"Загружено {len(prompts)} промтов")

        except Exception as e:
            logger.error(f"Ошибка загрузки промтов: {e}", exc_info=True)

    # Delegate to mixin
    async def _process_model_actions(self, actions: list):
        """Process model actions (delegated to mixin)"""
        await self.process_model_actions(actions)

    def _on_files_selection_changed(self, selected_files: list[dict]):
        """Handle file selection change in right panel"""
        # Sync selected files to chat panel
        if self.chat_panel:
            self.chat_panel._selected_files.clear()
            for f in selected_files:
                name = f.get("name", "")
                if name:
                    self.chat_panel._selected_files[name] = f
            self.chat_panel._rebuild_file_chips()
