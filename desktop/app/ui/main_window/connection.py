"""Connection handling for main window"""

import asyncio
import logging
from pathlib import Path
from qasync import asyncSlot

from app.ui.settings_dialog import SettingsDialog
from app.services.api_client import APIClient
from app.services.realtime_client import RealtimeClient

logger = logging.getLogger(__name__)


class ConnectionMixin:
    """Mixin for server connection handling"""

    async def _auto_connect(self):
        """Auto-connect on startup"""
        await asyncio.sleep(0.5)

        if not SettingsDialog.is_configured():
            self.toast_manager.warning("⚙️ Приложение не настроено. Откройте 'Настройки'.")
        else:
            await self._on_connect()

    @asyncSlot()
    async def _on_connect(self):
        """Handle Connect action"""
        logger.info("=== НАЧАЛО ПОДКЛЮЧЕНИЯ ===")

        if not SettingsDialog.is_configured():
            logger.warning("Настройки не сконфигурированы")
            self.toast_manager.error("Сначала настройте подключение в 'Настройках'")
            self._on_open_settings()
            return

        self.toast_manager.info("Подключение к серверу...")
        if self.connection_status:
            self.connection_status.set_server_connecting()

        try:
            local_settings = SettingsDialog.get_settings()
            server_url = local_settings["server_url"]
            api_token = local_settings["api_token"]
            cache_dir = Path(local_settings["cache_dir"])

            logger.info(f"Подключение к серверу: {server_url}")

            # Step 1: Fetch configuration from server
            try:
                server_config = await APIClient.fetch_config(server_url, api_token)
                logger.info(
                    f"Конфигурация получена с сервера: client_id={server_config.get('client_id')}"
                )
            except Exception as e:
                if "401" in str(e):
                    self.toast_manager.error("Неверный API токен")
                    self._on_open_settings()
                    return
                raise

            # Save server config locally for quick access
            SettingsDialog.save_server_config(server_config)

            # Extract config values
            self.client_id = server_config.get("client_id", "default")
            supabase_url = server_config.get("supabase_url", "")
            supabase_key = server_config.get("supabase_key", "")
            r2_public_url = server_config.get("r2_public_base_url", "")
            default_model = server_config.get("default_model", "gemini-2.0-flash")

            logger.info(f"Используется client_id: {self.client_id}")

            from app.services.supabase_repo import SupabaseRepo
            from app.services.r2_async import R2AsyncClient

            # Step 2: Initialize Supabase repo (for local queries and realtime)
            self.supabase_repo = SupabaseRepo(supabase_url, supabase_key)

            # Step 3: Server mode - all LLM operations go through server
            self.server_mode = True
            self.api_client = APIClient(
                base_url=server_url,
                client_id=self.client_id,
                api_token=api_token,
            )

            # Step 4: Initialize Realtime client for live updates
            self.realtime_client = RealtimeClient(
                supabase_url=supabase_url,
                supabase_key=supabase_key,
                client_id=self.client_id,
            )

            # Connect realtime signals
            self.realtime_client.jobUpdated.connect(self._on_job_updated)
            self.realtime_client.messageReceived.connect(self._on_realtime_message)
            self.realtime_client.connectionStatusChanged.connect(self._on_realtime_status)

            # Connect to realtime
            await self.realtime_client.connect()

            # Gemini client not needed - server handles LLM
            self.gemini_client = None

            # Step 5: R2 client for loading files (read-only, using public URL)
            if r2_public_url:
                self.r2_client = R2AsyncClient(
                    r2_public_base_url=r2_public_url,
                    r2_endpoint="",  # Not needed for read-only
                    r2_bucket="",  # Not needed for read-only
                    r2_access_key="",
                    r2_secret_key="",
                    local_cache_dir=cache_dir,
                )
            else:
                self.r2_client = None
                self.toast_manager.warning("R2 не настроен на сервере")

            # Update trace store with Supabase repo and load history
            self.trace_store.supabase_repo = self.supabase_repo
            self.trace_store.client_id = self.client_id
            await self.trace_store.load_from_db()
            logger.info(f"[INSPECTOR] Loaded {self.trace_store.count()} traces from DB")

            # Agent not needed - server handles LLM
            self.agent = None

            # Update dock panels with services
            self._set_dock_services()

            # Load chats list
            if self.chats_dock:
                await self.chats_dock.refresh_chats()

            # Load Gemini files if conversation exists
            if self.chats_dock and self.current_conversation_id:
                conv_id = str(self.current_conversation_id)
                await self.chats_dock.refresh_files(conversation_id=conv_id)
                self._sync_files_to_chat()

            self._enable_actions()

            # Load tree with correct client_id
            if self.projects_dock:
                await self.projects_dock.load_roots(client_id=self.client_id)

            # Load all available models first, then set default
            await self._load_gemini_models()
            if self.chat_panel:
                self.chat_panel.set_default_model(default_model)

            await self._load_prompts()

            logger.info("=== ПОДКЛЮЧЕНИЕ УСПЕШНО ===")
            self.toast_manager.success(f"✓ Подключено как {self.client_id}")
            if self.connection_status:
                self.connection_status.set_server_connected(self.client_id)

        except Exception as e:
            logger.error(f"ОШИБКА ПОДКЛЮЧЕНИЯ: {e}", exc_info=True)
            self.toast_manager.error(f"Ошибка: {e}")
            if self.connection_status:
                self.connection_status.set_server_error(str(e))
            # Clear server config on error
            SettingsDialog.clear_server_config()
