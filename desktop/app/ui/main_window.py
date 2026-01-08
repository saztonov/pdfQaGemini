"""Main application window"""
from typing import Optional
from uuid import UUID
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QSplitter
from PySide6.QtCore import Qt, QTimer
from qasync import asyncSlot
from pathlib import Path
import asyncio
import logging

from app.ui.toast import ToastManager
from app.ui.left_projects_panel import LeftProjectsPanel
from app.ui.chat_panel import ChatPanel
from app.ui.right_context_panel import RightContextPanel
from app.ui.connection_status import ConnectionStatusWidget
from app.ui.main_window_handlers import MainWindowHandlers
from app.ui.main_window_actions import ModelActionsHandler
from app.ui.menu_setup import MenuSetupMixin
from app.services.agent import Agent
from app.services.pdf_render import PDFRenderer
from app.services.trace import TraceStore
from app.services.api_client import APIClient
from app.services.realtime_client import RealtimeClient, JobUpdate, MessageUpdate
from app.ui.model_inspector import ModelInspectorWindow
from app.ui.settings_dialog import SettingsDialog

logger = logging.getLogger(__name__)


class MainWindow(MenuSetupMixin, MainWindowHandlers, ModelActionsHandler, QMainWindow):
    """Main application window"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("pdfQaGemini")
        self.resize(1400, 800)

        # Toast manager
        self.toast_manager = ToastManager(self)

        # Application state
        self.client_id: str = "default"  # Will be loaded from settings
        self.current_conversation_id: Optional[UUID] = None
        self.context_node_ids: list[str] = []
        self.attached_gemini_files: list[dict] = []

        # Services (will be initialized on connect)
        self.supabase_repo = None
        self.r2_client = None
        self.gemini_client = None
        self.agent = None
        self.pdf_renderer = PDFRenderer()
        self.trace_store = TraceStore(maxsize=200)  # R2 client will be set in connect

        # Server API clients (when server_url is configured)
        self.api_client: Optional[APIClient] = None
        self.realtime_client: Optional[RealtimeClient] = None
        self.server_mode: bool = False  # True when using server API
        self._pending_request: Optional[dict] = None  # For tracing in server mode

        # Inspector window (singleton)
        self.inspector_window: Optional[ModelInspectorWindow] = None

        # UI Components
        self.left_panel: Optional[LeftProjectsPanel] = None
        self.chat_panel: Optional[ChatPanel] = None
        self.right_panel: Optional[RightContextPanel] = None
        self.connection_status: Optional[ConnectionStatusWidget] = None

        self._setup_ui()
        self._connect_signals()

        # Auto-connect after event loop starts
        QTimer.singleShot(500, lambda: asyncio.create_task(self._auto_connect()))

    def _setup_ui(self):
        """Initialize UI components"""
        self._setup_menu()

        central = QWidget()
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        self.splitter = QSplitter(Qt.Horizontal)

        self.left_panel = LeftProjectsPanel(
            supabase_repo=self.supabase_repo, toast_manager=self.toast_manager
        )
        self.chat_panel = ChatPanel()
        self.right_panel = RightContextPanel(
            supabase_repo=self.supabase_repo,
            gemini_client=self.gemini_client,
            r2_client=self.r2_client,
            toast_manager=self.toast_manager,
            trace_store=self.trace_store,
        )

        self.splitter.addWidget(self.left_panel)
        self.splitter.addWidget(self.chat_panel)
        self.splitter.addWidget(self.right_panel)

        self.splitter.setSizes([280, 700, 420])

        layout.addWidget(self.splitter)

        # Connection status bar at bottom right
        self.connection_status = ConnectionStatusWidget(self)
        layout.addWidget(self.connection_status)

    def _connect_signals(self):
        """Connect panel signals"""
        if self.left_panel:
            self.left_panel.addToContextRequested.connect(self._on_nodes_add_context)
            self.left_panel.addFilesToContextRequested.connect(self._on_files_add_context)

        if self.right_panel:
            self.right_panel.refreshGeminiRequested.connect(self._on_refresh_gemini_async)
            self.right_panel.filesSelectionChanged.connect(self._on_files_selection_changed)
            self.right_panel.filesListChanged.connect(self._sync_files_to_chat)
            self.right_panel.chatSelected.connect(self._on_chat_selected)
            self.right_panel.chatCreated.connect(self._on_chat_created)
            self.right_panel.chatDeleted.connect(self._on_chat_deleted)

        if self.chat_panel:
            self.chat_panel.askModelRequested.connect(self._on_ask_model)
            self.chat_panel.editPromptRequested.connect(self._on_edit_prompt_from_chat)

    @asyncSlot()
    async def _on_refresh_gemini_async(self):
        """Async refresh Gemini files"""
        if self.right_panel:
            await self.right_panel.refresh_files()
            self._sync_files_to_chat()

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

    # Toolbar handlers

    async def _auto_connect(self):
        """Auto-connect on startup"""
        await asyncio.sleep(0.5)

        if not SettingsDialog.is_configured():
            self.toast_manager.warning("⚙️ Приложение не настроено. Откройте 'Настройки'.")
        else:
            await self._on_connect()

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
            self.supabase_repo, self.r2_client, self.toast_manager, self, client_id=self.client_id
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
            self.supabase_repo, self.r2_client, self.toast_manager, self, client_id=self.client_id
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
                logger.info(f"Конфигурация получена с сервера: client_id={server_config.get('client_id')}")
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
                    r2_bucket="",    # Not needed for read-only
                    r2_access_key="",
                    r2_secret_key="",
                    local_cache_dir=cache_dir,
                )
            else:
                self.r2_client = None
                self.toast_manager.warning("R2 не настроен на сервере")

            # Update trace store with R2 client
            self.trace_store.r2_client = self.r2_client
            self.trace_store.client_id = self.client_id

            # Agent not needed - server handles LLM
            self.agent = None

            # Update panels with services
            if self.left_panel:
                self.left_panel.set_services(self.supabase_repo, self.r2_client, self.toast_manager)

            if self.right_panel:
                self.right_panel.set_services(
                    self.supabase_repo, self.gemini_client, self.r2_client, self.toast_manager,
                    client_id=self.client_id,
                    api_client=self.api_client,
                    server_mode=self.server_mode,
                )
                self.right_panel.trace_store = self.trace_store
                logger.info(f"[INSPECTOR] trace_store assigned to right_panel, count={self.trace_store.count()}")

            # Load chats list
            if self.right_panel:
                await self.right_panel.refresh_chats()

            # Load Gemini files if conversation exists
            if self.right_panel and self.current_conversation_id:
                conv_id = str(self.current_conversation_id)
                await self.right_panel.refresh_files(conversation_id=conv_id)
                self._sync_files_to_chat()

            self._enable_actions()

            # Load tree with correct client_id
            if self.left_panel:
                await self.left_panel.load_roots(client_id=self.client_id)

            # Set default model in chat panel
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
                if self.right_panel:
                    await self.right_panel.refresh_chats()

                self.toast_manager.info("Создан новый чат")
            except Exception as e:
                logger.error(f"Ошибка создания разговора: {e}", exc_info=True)
                self.toast_manager.error(f"Ошибка создания разговора: {e}")

    def _enable_actions(self):
        """Enable actions after connect"""
        self.action_refresh_tree.setEnabled(True)
        self.action_upload.setEnabled(True)
        self.action_refresh_gemini.setEnabled(True)
        self.action_prompts.setEnabled(True)

    @asyncSlot()
    async def _on_refresh_tree(self):
        """Refresh projects tree"""
        self.toast_manager.info("Обновление дерева...")
        if self.left_panel:
            await self.left_panel.load_roots(client_id=self.client_id)
            self.toast_manager.success("✓ Дерево обновлено")

    @asyncSlot()
    async def _on_upload_selected(self):
        """Upload selected items from tree to Gemini"""
        if self.left_panel:
            await self.left_panel.add_selected_to_context()

    @asyncSlot()
    async def _on_refresh_gemini(self):
        """Refresh Gemini Files list"""
        if self.right_panel:
            conv_id = str(self.current_conversation_id) if self.current_conversation_id else None
            await self.right_panel.refresh_files(conversation_id=conv_id)
            self._sync_files_to_chat()
            # Refresh chats list to update file count
            await self.right_panel.refresh_chats()

    def _on_open_inspector(self):
        """Open Model Inspector window"""
        if not self.inspector_window:
            self.inspector_window = ModelInspectorWindow(self.trace_store, self)

        self.inspector_window.show()
        self.inspector_window.raise_()
        self.inspector_window.activateWindow()

    def _toggle_left_panel(self):
        """Toggle left panel visibility"""
        if self.left_panel:
            is_visible = self.left_panel.isVisible()
            self.left_panel.setVisible(not is_visible)
            self.action_toggle_left.setChecked(not is_visible)

    def _toggle_right_panel(self):
        """Toggle right panel visibility"""
        if self.right_panel:
            is_visible = self.right_panel.isVisible()
            self.right_panel.setVisible(not is_visible)
            self.action_toggle_right.setChecked(not is_visible)

    async def _load_gemini_models(self):
        """Load available Gemini models"""
        if not self.gemini_client:
            return

        try:
            models = await self.gemini_client.list_models()

            if self.chat_panel and models:
                self.chat_panel.set_models(models)
                self.toast_manager.success(f"Загружено {len(models)} моделей")

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

    # Chat management

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
                        "timestamp": format_time(msg.created_at, "%H:%M:%S")
                        if msg.created_at
                        else "",
                    }
                )

            # Load history to chat panel
            if self.chat_panel:
                self.chat_panel.load_history(chat_messages)

            # Sync files to chat (files already loaded in ChatListItem)
            if self.right_panel:
                self._sync_files_to_chat()

            logger.info(f"Чат загружен: {len(messages)} сообщений")

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

    # === Realtime handlers (server mode) ===

    def _on_job_updated(self, job_update: JobUpdate):
        """Handle job status update from realtime"""
        logger.info(f"Job update received: {job_update.job_id} -> {job_update.status}")

        # Only process if this is for the current conversation
        if self.current_conversation_id and job_update.conversation_id != str(self.current_conversation_id):
            return

        if job_update.status == "completed":
            # Job completed - hide loading indicator and enable input
            if self.chat_panel:
                self.chat_panel.set_loading(False)
                self.chat_panel.set_input_enabled(True)

            # Note: Don't show result_text here - it will come via _on_realtime_message
            # to avoid duplicate messages. Only log completion.
            logger.info(f"Job {job_update.job_id} completed")

        elif job_update.status == "failed":
            # Job failed - show error and enable input
            if self.chat_panel:
                self.chat_panel.set_loading(False)
                self.chat_panel.set_input_enabled(True)
                self.chat_panel.add_system_message(
                    f"Ошибка: {job_update.error_message or 'Неизвестная ошибка'}",
                    "error"
                )

            error_msg = job_update.error_message or "Неизвестная ошибка"
            self.toast_manager.error(f"Ошибка: {error_msg}")
            logger.error(f"Job {job_update.job_id} failed: {error_msg}")

        elif job_update.status == "processing":
            # Job started processing
            logger.info(f"Job {job_update.job_id} is processing")

    def _on_realtime_message(self, message_update: MessageUpdate):
        """Handle new message from realtime"""
        logger.info(f"[INSPECTOR] _on_realtime_message called: {message_update.message_id}, role={message_update.role}")

        # Only process if this is for the current conversation
        if self.current_conversation_id and message_update.conversation_id != str(self.current_conversation_id):
            return

        # Add message to chat panel
        if self.chat_panel and message_update.role == "assistant":
            from app.utils.time_utils import format_time
            from datetime import datetime

            # Hide loading and enable input
            self.chat_panel.set_loading(False)
            self.chat_panel.set_input_enabled(True)

            self.chat_panel.add_message(
                role="assistant",
                content=message_update.content,
                meta=message_update.meta,
                timestamp=format_time(datetime.utcnow(), "%H:%M:%S"),
            )

            self.toast_manager.success("✓ Ответ получен")

            # Create trace for inspector
            self._create_trace_from_response(message_update)

            # Process actions if present
            if message_update.meta and message_update.meta.get("actions"):
                actions = message_update.meta["actions"]
                asyncio.create_task(self._process_model_actions(actions))

    def _create_trace_from_response(self, message_update: MessageUpdate):
        """Create a trace from server response for inspector"""
        from datetime import datetime
        from app.services.trace import ModelTrace

        logger.info(f"[INSPECTOR] _create_trace_from_response called, pending_request={self._pending_request is not None}")

        if not self._pending_request:
            logger.warning("[INSPECTOR] No pending request for trace - skipping")
            return

        try:
            meta = message_update.meta or {}
            request_ts = self._pending_request.get("ts", datetime.utcnow())
            response_ts = datetime.utcnow()
            latency_ms = (response_ts - request_ts).total_seconds() * 1000

            # Build file refs for trace
            file_refs = self._pending_request.get("file_refs", [])
            input_files = [
                {
                    "name": f.get("name", ""),
                    "uri": f.get("uri", ""),
                    "mime_type": f.get("mime_type", ""),
                    "display_name": f.get("display_name", ""),
                }
                for f in file_refs
            ]

            trace = ModelTrace(
                ts=request_ts,
                conversation_id=self.current_conversation_id,
                model=self._pending_request.get("model_name", "unknown"),
                thinking_level=self._pending_request.get("thinking_level", "low"),
                system_prompt=self._pending_request.get("system_prompt", ""),
                user_text=self._pending_request.get("user_text", ""),
                input_files=input_files,
                response_json={"assistant_text": message_update.content, "actions": meta.get("actions", [])},
                parsed_actions=meta.get("actions", []),
                latency_ms=latency_ms,
                is_final=meta.get("is_final", True),
                assistant_text=message_update.content,
                full_thoughts=meta.get("thoughts", ""),
                input_tokens=meta.get("input_tokens"),
                output_tokens=meta.get("output_tokens"),
                total_tokens=meta.get("total_tokens"),
            )

            self.trace_store.add(trace)
            logger.info(f"[INSPECTOR] Trace created and added: {trace.id}, total traces: {self.trace_store.count()}")

            # Clear pending request
            self._pending_request = None

        except Exception as e:
            logger.error(f"[INSPECTOR] Failed to create trace: {e}", exc_info=True)

    def _on_realtime_status(self, is_connected: bool):
        """Handle realtime connection status change"""
        if is_connected:
            logger.info("Realtime connected")
            if self.connection_status:
                self.connection_status.set_server_connected(self.client_id)
        else:
            logger.warning("Realtime disconnected")
            self.toast_manager.warning("Соединение с сервером потеряно")
            if self.connection_status:
                self.connection_status.set_server_disconnected()

    async def closeEvent(self, event):
        """Clean up on window close"""
        # Stop connection checker
        if self.connection_status:
            self.connection_status.cleanup()

        # Disconnect realtime client
        if self.realtime_client:
            await self.realtime_client.disconnect()

        # Close API client
        if self.api_client:
            await self.api_client.close()

        # Close R2 client
        if self.r2_client:
            await self.r2_client.close()

        event.accept()
