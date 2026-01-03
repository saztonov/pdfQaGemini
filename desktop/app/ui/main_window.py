"""Main application window"""
from typing import Optional
from uuid import UUID
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QSplitter
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction
from qasync import asyncSlot
from pathlib import Path
import asyncio
import logging

from app.ui.toast import ToastManager
from app.ui.left_projects_panel import LeftProjectsPanel
from app.ui.chat_panel import ChatPanel
from app.ui.right_context_panel import RightContextPanel
from app.ui.main_window_handlers import MainWindowHandlers
from app.ui.main_window_actions import ModelActionsHandler
from app.services.agent import Agent
from app.services.pdf_render import PDFRenderer
from app.services.trace import TraceStore
from app.ui.model_inspector import ModelInspectorWindow
from app.ui.settings_dialog import SettingsDialog

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow, MainWindowHandlers, ModelActionsHandler):
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

        # Inspector window (singleton)
        self.inspector_window: Optional[ModelInspectorWindow] = None

        # UI Components
        self.left_panel: Optional[LeftProjectsPanel] = None
        self.chat_panel: Optional[ChatPanel] = None
        self.right_panel: Optional[RightContextPanel] = None

        self._setup_ui()
        self._connect_signals()

        # Auto-connect after event loop starts
        QTimer.singleShot(500, lambda: asyncio.create_task(self._auto_connect()))

    def _setup_ui(self):
        """Initialize UI components"""
        self._create_menu()

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

    def _create_menu(self):
        """Create main menu"""
        menubar = self.menuBar()

        # Меню "Файл"
        file_menu = menubar.addMenu("Файл")

        self.action_connect = QAction("Подключиться", self)
        self.action_connect.setShortcut("F5")
        self.action_connect.setToolTip("Загрузить настройки и подключиться")
        self.action_connect.triggered.connect(self._on_connect)
        file_menu.addAction(self.action_connect)

        file_menu.addSeparator()

        self.action_upload = QAction("Загрузить в Gemini", self)
        self.action_upload.setShortcut("Ctrl+U")
        self.action_upload.setToolTip("Загрузить выбранные файлы в Gemini Files")
        self.action_upload.triggered.connect(self._on_upload_selected)
        self.action_upload.setEnabled(False)
        file_menu.addAction(self.action_upload)

        file_menu.addSeparator()

        action_exit = QAction("Выход", self)
        action_exit.setShortcut("Alt+F4")
        action_exit.triggered.connect(self.close)
        file_menu.addAction(action_exit)

        # Меню "Вид"
        view_menu = menubar.addMenu("Вид")

        self.action_refresh_tree = QAction("Обновить дерево проектов", self)
        self.action_refresh_tree.setShortcut("Ctrl+R")
        self.action_refresh_tree.setToolTip("Обновить дерево проектов")
        self.action_refresh_tree.triggered.connect(self._on_refresh_tree)
        self.action_refresh_tree.setEnabled(False)
        view_menu.addAction(self.action_refresh_tree)

        self.action_refresh_gemini = QAction("Обновить Gemini Files", self)
        self.action_refresh_gemini.setShortcut("Ctrl+Shift+R")
        self.action_refresh_gemini.setToolTip("Обновить список Gemini Files")
        self.action_refresh_gemini.triggered.connect(self._on_refresh_gemini)
        self.action_refresh_gemini.setEnabled(False)
        view_menu.addAction(self.action_refresh_gemini)

        view_menu.addSeparator()

        self.action_model_inspector = QAction("🔍 Инспектор модели", self)
        self.action_model_inspector.setShortcut("Ctrl+I")
        self.action_model_inspector.setToolTip("Открыть инспектор модели с полными логами, мыслями и токенами")
        self.action_model_inspector.triggered.connect(self._on_open_inspector)
        view_menu.addAction(self.action_model_inspector)

        view_menu.addSeparator()

        # Подменю "Панели"
        panels_menu = view_menu.addMenu("Панели")

        self.action_toggle_left = QAction("Панель проектов", self)
        self.action_toggle_left.setCheckable(True)
        self.action_toggle_left.setChecked(True)
        self.action_toggle_left.setShortcut("Ctrl+1")
        self.action_toggle_left.triggered.connect(self._toggle_left_panel)
        panels_menu.addAction(self.action_toggle_left)

        self.action_toggle_right = QAction("Панель контекста", self)
        self.action_toggle_right.setCheckable(True)
        self.action_toggle_right.setChecked(True)
        self.action_toggle_right.setShortcut("Ctrl+2")
        self.action_toggle_right.triggered.connect(self._toggle_right_panel)
        panels_menu.addAction(self.action_toggle_right)

        # Меню "Настройки"
        settings_menu = menubar.addMenu("Настройки")

        self.action_settings = QAction("Настройки подключения", self)
        self.action_settings.setShortcut("Ctrl+,")
        self.action_settings.setToolTip("Настройки подключения")
        self.action_settings.triggered.connect(self._on_open_settings)
        settings_menu.addAction(self.action_settings)

        settings_menu.addSeparator()

        self.action_prompts = QAction("Промты", self)
        self.action_prompts.setShortcut("Ctrl+P")
        self.action_prompts.setToolTip("Управление промтами")
        self.action_prompts.triggered.connect(self._on_open_prompts)
        self.action_prompts.setEnabled(False)
        settings_menu.addAction(self.action_prompts)

    def _connect_signals(self):
        """Connect panel signals"""
        if self.left_panel:
            self.left_panel.addToContextRequested.connect(self._on_nodes_add_context)
            self.left_panel.addFilesToContextRequested.connect(self._on_files_add_context)

        if self.right_panel:
            self.right_panel.refreshGeminiRequested.connect(self._on_refresh_gemini_async)
            self.right_panel.filesSelectionChanged.connect(self._on_files_selection_changed)
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
            self.toast_manager.success(
                "Настройки сохранены. Нажмите 'Подключиться' для применения."
            )

    @asyncSlot()
    async def _on_open_prompts(self):
        """Open prompts management dialog"""
        if not self.supabase_repo:
            self.toast_manager.error("Сначала подключитесь к базе данных")
            return

        from app.ui.prompts_dialog import PromptsDialog

        dialog = PromptsDialog(self.supabase_repo, self.r2_client, self.toast_manager, self)
        await dialog.load_prompts()
        result = dialog.exec()

        # Reload prompts in chat panel after dialog closes
        if result and self.chat_panel:
            await self._load_prompts()

    @asyncSlot(str)
    async def _on_edit_prompt_from_chat(self, prompt_id: str):
        """Open prompts dialog to edit specific prompt"""
        if not self.supabase_repo:
            self.toast_manager.error("Сначала подключитесь к базе данных")
            return

        from app.ui.prompts_dialog import PromptsDialog

        dialog = PromptsDialog(self.supabase_repo, self.r2_client, self.toast_manager, self)
        await dialog.load_prompts()

        # Select the prompt in the dialog
        for i in range(dialog.prompts_list.count()):
            item = dialog.prompts_list.item(i)
            if item.data(Qt.UserRole) == prompt_id:
                dialog.prompts_list.setCurrentItem(item)
                dialog._on_prompt_selected(item)
                break

        result = dialog.exec()

        # Reload prompts in chat panel after dialog closes
        if result and self.chat_panel:
            await self._load_prompts()

    @asyncSlot()
    async def _on_connect(self):
        """Handle Connect action"""
        logger.info("=== НАЧАЛО ПОДКЛЮЧЕНИЯ ===")

        if not SettingsDialog.is_configured():
            logger.warning("Настройки не сконфигурированы")
            self.toast_manager.error("Сначала настройте подключение в 'Настройках'")
            self._on_open_settings()
            return

        self.toast_manager.info("Подключение...")

        try:
            config = SettingsDialog.get_settings()
            logger.info("Конфигурация загружена")

            # Save client_id from settings
            self.client_id = config.get("client_id", "default")
            logger.info(f"Используется client_id: {self.client_id}")

            supabase_url = config["supabase_url"]
            supabase_key = config["supabase_key"]
            gemini_api_key = config["gemini_api_key"]

            from app.services.supabase_repo import SupabaseRepo
            from app.services.gemini_client import GeminiClient
            from app.services.r2_async import R2AsyncClient

            self.supabase_repo = SupabaseRepo(supabase_url, supabase_key)
            self.gemini_client = GeminiClient(gemini_api_key)

            r2_public = config["r2_public_base_url"]
            r2_endpoint = config["r2_endpoint"]
            r2_bucket = config["r2_bucket"]
            r2_access = config["r2_access_key"]
            r2_secret = config["r2_secret_key"]
            cache_dir = Path(config["cache_dir"])

            if all([r2_public, r2_endpoint, r2_bucket, r2_access, r2_secret]):
                self.r2_client = R2AsyncClient(
                    r2_public_base_url=r2_public,
                    r2_endpoint=r2_endpoint,
                    r2_bucket=r2_bucket,
                    r2_access_key=r2_access,
                    r2_secret_key=r2_secret,
                    local_cache_dir=cache_dir,
                )
            else:
                self.toast_manager.warning("R2 не настроен")

            # Update trace store with R2 client
            self.trace_store.r2_client = self.r2_client
            self.trace_store.client_id = self.client_id

            self.agent = Agent(
                self.gemini_client,
                self.supabase_repo,
                trace_store=self.trace_store,
            )

            # Update panels with services
            if self.left_panel:
                self.left_panel.set_services(self.supabase_repo, self.r2_client, self.toast_manager)

            if self.right_panel:
                self.right_panel.set_services(
                    self.supabase_repo, self.gemini_client, self.r2_client, self.toast_manager,
                    client_id=self.client_id
                )
                self.right_panel.trace_store = self.trace_store

            # Load chats list
            if self.right_panel:
                await self.right_panel.refresh_chats()

            # Don't create conversation automatically - it will be created on first message
            # Just load files

            # Load Gemini files and sync to chat
            if self.right_panel and self.current_conversation_id:
                conv_id = str(self.current_conversation_id)
                await self.right_panel.refresh_files(conversation_id=conv_id)
                self._sync_files_to_chat()

            self._enable_actions()

            # Load tree with correct client_id
            if self.left_panel:
                await self.left_panel.load_roots(client_id=self.client_id)

            await self._load_gemini_models()
            await self._load_prompts()

            logger.info("=== ПОДКЛЮЧЕНИЕ УСПЕШНО ===")
            self.toast_manager.success("✓ Подключено")

        except Exception as e:
            logger.error(f"ОШИБКА ПОДКЛЮЧЕНИЯ: {e}", exc_info=True)
            self.toast_manager.error(f"Ошибка: {e}")

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

            # Refresh Gemini files (filtered by current chat)
            if self.right_panel:
                await self.right_panel.refresh_files(conversation_id=conversation_id)
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
