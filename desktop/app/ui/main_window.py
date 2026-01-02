"""Main application window"""
from typing import Optional
from uuid import UUID
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QSplitter, QToolBar
)
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
from app.models.schemas import ContextItem
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
        self.current_conversation_id: Optional[UUID] = None
        self.context_node_ids: list[str] = []
        self.context_items: list[ContextItem] = []
        self.attached_gemini_files: list[dict] = []
        
        # Services (will be initialized on connect)
        self.supabase_repo = None
        self.r2_client = None
        self.gemini_client = None
        self.agent = None
        self.pdf_renderer = PDFRenderer()
        self.trace_store = TraceStore(maxsize=200)
        
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
        self._create_toolbar()
        
        central = QWidget()
        self.setCentralWidget(central)
        
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        
        splitter = QSplitter(Qt.Horizontal)
        
        self.left_panel = LeftProjectsPanel(
            supabase_repo=self.supabase_repo,
            toast_manager=self.toast_manager
        )
        self.chat_panel = ChatPanel()
        self.right_panel = RightContextPanel(
            supabase_repo=self.supabase_repo,
            gemini_client=self.gemini_client,
            r2_client=self.r2_client,
            toast_manager=self.toast_manager
        )
        
        splitter.addWidget(self.left_panel)
        splitter.addWidget(self.chat_panel)
        splitter.addWidget(self.right_panel)
        
        splitter.setSizes([280, 700, 420])
        
        layout.addWidget(splitter)
    
    def _create_toolbar(self):
        """Create main toolbar"""
        toolbar = QToolBar("Панель инструментов")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        
        self.action_connect = QAction("Подключиться", self)
        self.action_connect.setToolTip("Загрузить настройки и подключиться")
        self.action_connect.triggered.connect(self._on_connect)
        toolbar.addAction(self.action_connect)
        
        toolbar.addSeparator()
        
        self.action_refresh_tree = QAction("Обновить дерево", self)
        self.action_refresh_tree.setToolTip("Обновить дерево проектов")
        self.action_refresh_tree.triggered.connect(self._on_refresh_tree)
        self.action_refresh_tree.setEnabled(False)
        toolbar.addAction(self.action_refresh_tree)
        
        self.action_add_context = QAction("Добавить в контекст", self)
        self.action_add_context.setToolTip("Добавить выбранные узлы в контекст")
        self.action_add_context.triggered.connect(self._on_add_to_context)
        self.action_add_context.setEnabled(False)
        toolbar.addAction(self.action_add_context)
        
        toolbar.addSeparator()
        
        self.action_refresh_gemini = QAction("Обновить Gemini Files", self)
        self.action_refresh_gemini.setToolTip("Обновить список Gemini Files")
        self.action_refresh_gemini.triggered.connect(self._on_refresh_gemini)
        self.action_refresh_gemini.setEnabled(False)
        toolbar.addAction(self.action_refresh_gemini)
        
        toolbar.addSeparator()
        
        self.action_model_inspector = QAction("Инспектор модели", self)
        self.action_model_inspector.setToolTip("Открыть инспектор логов модели")
        self.action_model_inspector.triggered.connect(self._on_open_inspector)
        toolbar.addAction(self.action_model_inspector)
        
        toolbar.addSeparator()
        
        self.action_settings = QAction("Настройки", self)
        self.action_settings.setToolTip("Настройки подключения")
        self.action_settings.triggered.connect(self._on_open_settings)
        toolbar.addAction(self.action_settings)
    
    def _connect_signals(self):
        """Connect panel signals"""
        if self.left_panel:
            self.left_panel.addToContextRequested.connect(self._on_nodes_add_context)
            self.left_panel.addFilesToContextRequested.connect(self._on_files_add_context)
        
        if self.right_panel:
            self.right_panel.uploadContextItemsRequested.connect(self._on_upload_context_items)
            self.right_panel.refreshGeminiRequested.connect(self._on_refresh_gemini)
        
        if self.chat_panel:
            self.chat_panel.askModelRequested.connect(self._on_ask_model)
    
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
            self.toast_manager.success("Настройки сохранены. Нажмите 'Подключиться' для применения.")
    
    @asyncSlot()
    async def _on_connect(self):
        """Handle Connect action"""
        logger.info("=== НАЧАЛО ПОДКЛЮЧЕНИЯ ===")
        
        if not SettingsDialog.is_configured():
            logger.warning("Настройки не сконфигурированы")
            self.toast_manager.error("Сначала настройте подключение в 'Настройках'")
            self._on_open_settings()
            return
        
        self.toast_manager.info("Подключение: загрузка настроек...")
        
        try:
            config = SettingsDialog.get_settings()
            logger.info(f"Конфигурация загружена: supabase_url={config['supabase_url'][:30]}...")
            
            supabase_url = config["supabase_url"]
            supabase_key = config["supabase_key"]
            gemini_api_key = config["gemini_api_key"]
            
            from app.services.supabase_repo import SupabaseRepo
            from app.services.gemini_client import GeminiClient
            from app.services.r2_async import R2AsyncClient
            
            logger.info("Инициализация SupabaseRepo...")
            self.supabase_repo = SupabaseRepo(supabase_url, supabase_key)
            logger.info("SupabaseRepo создан успешно")
            
            logger.info("Инициализация GeminiClient...")
            self.gemini_client = GeminiClient(gemini_api_key)
            logger.info("GeminiClient создан успешно")
            
            r2_public = config["r2_public_base_url"]
            r2_endpoint = config["r2_endpoint"]
            r2_bucket = config["r2_bucket"]
            r2_access = config["r2_access_key"]
            r2_secret = config["r2_secret_key"]
            cache_dir = Path(config["cache_dir"])
            
            logger.info(f"R2 конфигурация: public={bool(r2_public)}, endpoint={bool(r2_endpoint)}, bucket={bool(r2_bucket)}")
            
            if all([r2_public, r2_endpoint, r2_bucket, r2_access, r2_secret]):
                logger.info("Инициализация R2AsyncClient...")
                self.r2_client = R2AsyncClient(
                    r2_public_base_url=r2_public,
                    r2_endpoint=r2_endpoint,
                    r2_bucket=r2_bucket,
                    r2_access_key=r2_access,
                    r2_secret_key=r2_secret,
                    local_cache_dir=cache_dir,
                )
                logger.info("R2AsyncClient создан успешно")
            else:
                logger.warning("R2 не настроен (опционально)")
                self.toast_manager.warning("R2 не настроен (опционально)")
            
            logger.info("Инициализация Agent...")
            self.agent = Agent(
                self.gemini_client,
                self.supabase_repo,
                trace_store=self.trace_store,
            )
            logger.info("Agent создан успешно")
            
            logger.info("Обновление панелей с сервисами...")
            if self.left_panel:
                logger.info("Установка сервисов для left_panel...")
                self.left_panel.set_services(self.supabase_repo, self.r2_client, self.toast_manager)
                logger.info(f"left_panel.supabase_repo установлен: {self.left_panel.supabase_repo is not None}")
            
            if self.right_panel:
                logger.info("Установка сервисов для right_panel...")
                self.right_panel.set_services(self.supabase_repo, self.gemini_client, self.r2_client, self.toast_manager)
                logger.info("right_panel сервисы установлены")
            
            logger.info("Создание/загрузка диалога...")
            await self._ensure_conversation()
            
            if self.right_panel and self.current_conversation_id:
                self.right_panel.conversation_id = str(self.current_conversation_id)
                await self.right_panel.load_context_from_db()
                self._sync_attached_gemini_files()
            
            logger.info("Включение действий...")
            self._enable_actions()
            
            logger.info("Автоматическая загрузка дерева...")
            if self.left_panel:
                await self.left_panel.load_roots()
            
            await self._load_gemini_models()
            
            logger.info("=== ПОДКЛЮЧЕНИЕ УСПЕШНО ===")
            self.toast_manager.success("Подключено успешно")
        
        except Exception as e:
            logger.error(f"ОШИБКА ПОДКЛЮЧЕНИЯ: {e}", exc_info=True)
            self.toast_manager.error(f"Ошибка подключения: {e}")
    
    async def _ensure_conversation(self):
        """Ensure conversation exists"""
        if not self.current_conversation_id and self.supabase_repo:
            try:
                conv = await self.supabase_repo.qa_create_conversation(
                    title="Новый чат",
                )
                self.current_conversation_id = conv.id
                
                if self.right_panel:
                    self.right_panel.conversation_id = str(self.current_conversation_id)
                    await self.right_panel.load_context_from_db()
                    self._sync_attached_gemini_files()
                
                self.toast_manager.info(f"Создан новый диалог: {conv.id}")
            except Exception as e:
                self.toast_manager.error(f"Ошибка создания разговора: {e}")
    
    def _sync_attached_gemini_files(self):
        """Sync attached_gemini_files from right_panel context items"""
        self.attached_gemini_files.clear()
        if self.right_panel:
            for item in self.right_panel.context_items:
                if item.gemini_uri and item.gemini_name:
                    self.attached_gemini_files.append({
                        "gemini_name": item.gemini_name,
                        "gemini_uri": item.gemini_uri,
                        "context_item_id": item.id,
                        "mime_type": item.mime_type,
                    })
        logger.info(f"Синхронизировано {len(self.attached_gemini_files)} файлов Gemini")
    
    def _enable_actions(self):
        """Enable actions after connect"""
        self.action_refresh_tree.setEnabled(True)
        self.action_add_context.setEnabled(True)
        self.action_refresh_gemini.setEnabled(True)
    
    @asyncSlot()
    async def _on_refresh_tree(self):
        """Refresh projects tree"""
        logger.info("=== ОБНОВЛЕНИЕ ДЕРЕВА ===")
        self.toast_manager.info("Обновление дерева...")
        
        if not self.left_panel:
            logger.error("left_panel не существует")
            return
        
        logger.info(f"left_panel.supabase_repo установлен: {self.left_panel.supabase_repo is not None}")
        
        await self.left_panel.load_roots()
        self.toast_manager.success("Дерево обновлено")
    
    @asyncSlot()
    async def _on_add_to_context(self):
        """Add selected nodes to context (delegates to left panel)"""
        if self.left_panel:
            await self.left_panel.add_selected_to_context()
    
    def _on_refresh_gemini(self):
        """Refresh Gemini Files list"""
        self.toast_manager.info("Обновление Gemini Files...")
        self.toast_manager.success("Gemini Files обновлены")
    
    def _on_open_inspector(self):
        """Open Model Inspector window"""
        if not self.inspector_window:
            self.inspector_window = ModelInspectorWindow(self.trace_store, self)
        
        self.inspector_window.show()
        self.inspector_window.raise_()
        self.inspector_window.activateWindow()
    
    async def _load_gemini_models(self):
        """Load available Gemini models"""
        logger.info("=== ЗАГРУЗКА МОДЕЛЕЙ GEMINI ===")
        if not self.gemini_client:
            logger.warning("gemini_client не инициализирован")
            return
        
        try:
            self.toast_manager.info("Загрузка списка моделей...")
            models = await self.gemini_client.list_models()
            
            logger.info(f"Получено моделей от API: {len(models) if models else 0}")
            if models:
                for i, m in enumerate(models[:5]):
                    logger.info(f"  [{i}] name={m.get('name')}, display={m.get('display_name')}")
                if len(models) > 5:
                    logger.info(f"  ... и ещё {len(models) - 5} моделей")
            
            if self.chat_panel and models:
                logger.info(f"Вызов chat_panel.set_models с {len(models)} моделями")
                self.chat_panel.set_models(models)
                self.toast_manager.success(f"Загружено {len(models)} моделей")
            elif not models:
                logger.warning("Список моделей пуст")
                self.toast_manager.warning("Нет доступных моделей")
        
        except Exception as e:
            logger.error(f"Ошибка загрузки моделей: {e}", exc_info=True)
            self.toast_manager.error(f"Ошибка загрузки моделей: {e}")
    
    # Delegate to mixin
    async def _process_model_actions(self, actions: list):
        """Process model actions (delegated to mixin)"""
        await self.process_model_actions(actions)
