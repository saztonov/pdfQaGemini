"""Settings and prompts handlers for main window"""

import asyncio
import logging
from PySide6.QtCore import Qt

from app.ui.settings_dialog import SettingsDialog

logger = logging.getLogger(__name__)


class SettingsHandlersMixin:
    """Mixin for settings and prompts dialog handlers"""

    def _on_open_settings(self):
        """Open settings dialog"""
        dialog = SettingsDialog(self)
        if dialog.exec():
            self.toast_manager.success("Настройки сохранены. Переподключение...")
            asyncio.create_task(self._on_connect())

    def _on_open_prompts(self):
        """Open prompts management dialog"""
        if not self.supabase_repo:
            self.toast_manager.error("Сначала подключитесь к базе данных")
            return

        from app.ui.prompts_dialog import PromptsDialog

        dialog = PromptsDialog(
            self.supabase_repo,
            self.r2_client,
            self.toast_manager,
            self,
            client_id=self.client_id,
        )

        # Connect finished signal to reload prompts
        def on_dialog_finished(result):
            if result and self.chat_panel:
                asyncio.create_task(self._load_prompts())

        dialog.finished.connect(on_dialog_finished)

        # Show dialog as non-blocking modal
        dialog.open()

        # Load prompts after dialog is shown (@asyncSlot creates task automatically)
        dialog.load_prompts()

    def _on_edit_prompt_from_chat(self, prompt_id: str):
        """Open prompts dialog to edit specific prompt"""
        if not self.supabase_repo:
            self.toast_manager.error("Сначала подключитесь к базе данных")
            return

        from app.ui.prompts_dialog import PromptsDialog

        dialog = PromptsDialog(
            self.supabase_repo,
            self.r2_client,
            self.toast_manager,
            self,
            client_id=self.client_id,
        )

        # Connect finished signal to reload prompts
        def on_dialog_finished(result):
            if result and self.chat_panel:
                asyncio.create_task(self._load_prompts())

        dialog.finished.connect(on_dialog_finished)

        # Show dialog as non-blocking modal
        dialog.open()

        # Load prompts and select the specific one
        async def load_and_select():
            dialog.prompts = await self.supabase_repo.prompts_list(client_id=self.client_id)
            dialog._refresh_list()

            # Select the prompt in the dialog
            for i in range(dialog.prompts_list.count()):
                item = dialog.prompts_list.item(i)
                if item.data(Qt.UserRole) == prompt_id:
                    dialog.prompts_list.setCurrentItem(item)
                    dialog._on_prompt_selected(item)
                    break

        asyncio.create_task(load_and_select())
