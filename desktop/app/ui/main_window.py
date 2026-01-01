"""Main application window"""
from typing import Optional
from uuid import UUID
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QSplitter, QToolBar
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from app.ui.toast import ToastManager
from app.ui.left_projects_panel import LeftProjectsPanel
from app.ui.chat_panel import ChatPanel
from app.ui.right_context_panel import RightContextPanel
from app.models.schemas import ContextItem
from app.services.agent import Agent
from app.services.pdf_render import PDFRenderer
from app.services.trace import TraceStore
from app.ui.image_viewer import ImageViewerDialog
from app.ui.model_inspector import ModelInspectorWindow
from app.ui.settings_dialog import SettingsDialog
import asyncio
from qasync import asyncSlot
from pathlib import Path
import hashlib
from datetime import datetime
from PySide6.QtCore import QTimer
import logging

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("pdfQaGemini")
        self.resize(1400, 800)
        
        # Toast manager
        self.toast_manager = ToastManager(self)
        
        # Application state
        self.current_client_id: Optional[str] = None
        self.current_conversation_id: Optional[UUID] = None
        self.context_node_ids: list[str] = []
        self.context_items: list[ContextItem] = []
        self.attached_gemini_files: list[dict] = []  # {"gemini_name": ..., "gemini_uri": ...}
        
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
        
        # Check configuration after event loop starts (delay)
        QTimer.singleShot(500, lambda: asyncio.create_task(self._check_configuration()))
    
    def _setup_ui(self):
        """Initialize UI components"""
        # Toolbar
        self._create_toolbar()
        
        # Central widget with splitter
        central = QWidget()
        self.setCentralWidget(central)
        
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Main splitter: Left | Center | Right
        splitter = QSplitter(Qt.Horizontal)
        
        # Panels
        self.left_panel = LeftProjectsPanel(
            supabase_repo=self.supabase_repo,
            toast_manager=self.toast_manager
        )
        self.chat_panel = ChatPanel()
        self.right_panel = RightContextPanel(
            supabase_repo=self.supabase_repo,
            gemini_client=self.gemini_client,
            toast_manager=self.toast_manager
        )
        
        splitter.addWidget(self.left_panel)
        splitter.addWidget(self.chat_panel)
        splitter.addWidget(self.right_panel)
        
        # Set initial sizes: 20% | 50% | 30%
        splitter.setSizes([280, 700, 420])
        
        layout.addWidget(splitter)
    
    def _create_toolbar(self):
        """Create main toolbar"""
        toolbar = QToolBar("Панель инструментов")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        
        # Connect action
        self.action_connect = QAction("Подключиться", self)
        self.action_connect.setToolTip("Загрузить настройки и подключиться")
        self.action_connect.triggered.connect(self._on_connect)
        toolbar.addAction(self.action_connect)
        
        toolbar.addSeparator()
        
        # Refresh tree
        self.action_refresh_tree = QAction("Обновить дерево", self)
        self.action_refresh_tree.setToolTip("Обновить дерево проектов")
        self.action_refresh_tree.triggered.connect(self._on_refresh_tree)
        self.action_refresh_tree.setEnabled(False)
        toolbar.addAction(self.action_refresh_tree)
        
        # Add to context
        self.action_add_context = QAction("Добавить в контекст", self)
        self.action_add_context.setToolTip("Добавить выбранные узлы в контекст")
        self.action_add_context.triggered.connect(self._on_add_to_context)
        self.action_add_context.setEnabled(False)
        toolbar.addAction(self.action_add_context)
        
        toolbar.addSeparator()
        
        # Refresh Gemini Files
        self.action_refresh_gemini = QAction("Обновить Gemini Files", self)
        self.action_refresh_gemini.setToolTip("Обновить список Gemini Files")
        self.action_refresh_gemini.triggered.connect(self._on_refresh_gemini)
        self.action_refresh_gemini.setEnabled(False)
        toolbar.addAction(self.action_refresh_gemini)
        
        toolbar.addSeparator()
        
        # Model Inspector
        self.action_model_inspector = QAction("Инспектор модели", self)
        self.action_model_inspector.setToolTip("Открыть инспектор логов модели")
        self.action_model_inspector.triggered.connect(self._on_open_inspector)
        toolbar.addAction(self.action_model_inspector)
        
        toolbar.addSeparator()
        
        # Settings
        self.action_settings = QAction("Настройки", self)
        self.action_settings.setToolTip("Настройки подключения")
        self.action_settings.triggered.connect(self._on_open_settings)
        toolbar.addAction(self.action_settings)
    
    def _connect_signals(self):
        """Connect panel signals"""
        if self.left_panel:
            self.left_panel.addToContextRequested.connect(self._on_nodes_add_context)
        
        if self.right_panel:
            self.right_panel.uploadContextItemsRequested.connect(self._on_upload_context_items)
            self.right_panel.refreshGeminiRequested.connect(self._on_refresh_gemini)
        
        if self.chat_panel:
            self.chat_panel.askModelRequested.connect(self._on_ask_model)
    
    # Toolbar handlers
    
    async def _check_configuration(self):
        """Check if application is configured on startup"""
        # Small delay to let UI initialize
        await asyncio.sleep(0.5)
        
        if not SettingsDialog.is_configured():
            self.toast_manager.warning("⚙️ Приложение не настроено. Откройте 'Настройки'.")
            # Optionally auto-open settings
            # self._on_open_settings()
    
    def _on_open_settings(self):
        """Open settings dialog"""
        dialog = SettingsDialog(self)
        if dialog.exec():
            self.toast_manager.success("Настройки сохранены. Нажмите 'Подключиться' для применения.")
    
    @asyncSlot()
    async def _on_connect(self):
        """Handle Connect action"""
        logger.info("=== НАЧАЛО ПОДКЛЮЧЕНИЯ ===")
        
        # Check if configured
        if not SettingsDialog.is_configured():
            logger.warning("Настройки не сконфигурированы")
            self.toast_manager.error("Сначала настройте подключение в 'Настройках'")
            self._on_open_settings()
            return
        
        self.toast_manager.info("Подключение: загрузка настроек...")
        
        try:
            # Get config from QSettings
            config = SettingsDialog.get_settings()
            logger.info(f"Конфигурация загружена: client_id={config['client_id']}, supabase_url={config['supabase_url'][:30]}...")
            
            client_id = config["client_id"]
            supabase_url = config["supabase_url"]
            supabase_key = config["supabase_key"]
            gemini_api_key = config["gemini_api_key"]
            
            # Initialize services
            from app.services.supabase_repo import SupabaseRepo
            from app.services.gemini_client import GeminiClient
            from app.services.r2_async import R2AsyncClient
            
            logger.info("Инициализация SupabaseRepo...")
            self.supabase_repo = SupabaseRepo(supabase_url, supabase_key)
            logger.info("SupabaseRepo создан успешно")
            
            logger.info("Инициализация GeminiClient...")
            self.gemini_client = GeminiClient(gemini_api_key)
            logger.info("GeminiClient создан успешно")
            
            # R2 (if configured)
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
            
            # Initialize agent with trace store
            logger.info("Инициализация Agent...")
            self.agent = Agent(
                self.gemini_client,
                self.supabase_repo,
                trace_store=self.trace_store,
                default_model=config["model_default"]
            )
            logger.info("Agent создан успешно")
            
            # Set client ID
            self.current_client_id = client_id
            logger.info(f"client_id установлен: {client_id}")
            
            # Update panels with services
            logger.info("Обновление панелей с сервисами...")
            if self.left_panel:
                logger.info("Установка сервисов для left_panel...")
                self.left_panel.set_services(self.supabase_repo, self.toast_manager)
                self.left_panel.client_input.setText(client_id)
                logger.info(f"left_panel.supabase_repo установлен: {self.left_panel.supabase_repo is not None}")
            
            if self.right_panel:
                logger.info("Установка сервисов для right_panel...")
                self.right_panel.set_services(self.supabase_repo, self.gemini_client, self.toast_manager)
                logger.info("right_panel сервисы установлены")
            
            # Create or load conversation
            logger.info("Создание/загрузка диалога...")
            await self._ensure_conversation()
            
            logger.info("Включение действий...")
            self._enable_actions()
            
            logger.info("=== ПОДКЛЮЧЕНИЕ УСПЕШНО ===")
            self.toast_manager.success("Подключено успешно")
        
        except Exception as e:
            logger.error(f"ОШИБКА ПОДКЛЮЧЕНИЯ: {e}", exc_info=True)
            self.toast_manager.error(f"Ошибка подключения: {e}")
    
    async def _ensure_conversation(self):
        """Ensure conversation exists"""
        if not self.current_conversation_id and self.supabase_repo and self.current_client_id:
            try:
                conv = await self.supabase_repo.qa_create_conversation(
                    client_id=self.current_client_id,
                    title="Новый чат",
                )
                self.current_conversation_id = conv.id
                self.toast_manager.info(f"Создан новый диалог: {conv.id}")
            except Exception as e:
                self.toast_manager.error(f"Ошибка создания разговора: {e}")
    
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
        
        if not self.current_client_id:
            logger.warning("current_client_id не установлен")
            self.toast_manager.error("Client ID не установлен. Нажмите 'Подключиться'")
            return
        
        if not self.left_panel:
            logger.error("left_panel не существует")
            return
        
        logger.info(f"Загрузка корневых узлов для client_id={self.current_client_id}")
        logger.info(f"left_panel.supabase_repo установлен: {self.left_panel.supabase_repo is not None}")
        
        await self.left_panel.load_roots(self.current_client_id)
        self.toast_manager.success("Дерево обновлено")
    
    def _on_add_to_context(self):
        """Add selected nodes to context"""
        if self.left_panel:
            node_ids = self.left_panel.get_selected_node_ids()
            if node_ids:
                self._on_nodes_add_context(node_ids)
            else:
                self.toast_manager.warning("Нет выбранных узлов")
    
    def _on_refresh_gemini(self):
        """Refresh Gemini Files list"""
        self.toast_manager.info("Обновление Gemini Files...")
        # TODO: Load from Gemini API
        self.toast_manager.success("Gemini Files обновлены")
    
    def _on_open_inspector(self):
        """Open Model Inspector window"""
        if not self.inspector_window:
            self.inspector_window = ModelInspectorWindow(self.trace_store, self)
        
        self.inspector_window.show()
        self.inspector_window.raise_()
        self.inspector_window.activateWindow()
    
    # Signal handlers
    
    def _on_nodes_add_context(self, node_ids: list[str]):
        """Handle add nodes to context"""
        self.toast_manager.info(f"Добавление {len(node_ids)} узлов в контекст...")
        
        # Add to context
        for node_id in node_ids:
            if node_id not in self.context_node_ids:
                self.context_node_ids.append(node_id)
        
        # Update right panel
        if self.right_panel:
            self.right_panel.set_context_node_ids(self.context_node_ids)
        
            self.toast_manager.success(f"Добавлено {len(node_ids)} узлов в контекст. Нажмите 'Загрузить файлы узлов' для загрузки.")
    
    @asyncSlot(list)
    async def _on_upload_context_items(self, item_ids: list):
        """Handle upload context items to Gemini"""
        if not self.gemini_client or not self.r2_client:
            self.toast_manager.error("Сервисы не инициализированы")
            return
        
        self.toast_manager.info(f"Загрузка {len(item_ids)} файлов в Gemini...")
        
        try:
            uploaded_count = 0
            
            for item_id in item_ids:
                # Get context item
                context_item = None
                for item in self.right_panel.context_items:
                    if item.id == item_id:
                        context_item = item
                        break
                
                if not context_item or not context_item.r2_key:
                    continue
                
                # Download from R2 to cache
                url = self.r2_client.build_public_url(context_item.r2_key)
                cached_path = await self.r2_client.download_to_cache(url, item_id)
                
                # Upload to Gemini
                result = await self.gemini_client.upload_file(
                    cached_path,
                    mime_type=context_item.mime_type,
                    display_name=context_item.title,
                )
                
                # Update context item
                gemini_name = result["name"]
                gemini_uri = result["uri"]
                
                if self.right_panel:
                    self.right_panel.update_context_item_status(
                        item_id,
                        "uploaded",
                        gemini_name
                    )
                
                # Add to attached files
                self.attached_gemini_files.append({
                    "gemini_name": gemini_name,
                    "gemini_uri": gemini_uri,
                    "context_item_id": item_id,
                })
                
                uploaded_count += 1
            
            self.toast_manager.success(f"Загружено {uploaded_count} файлов в Gemini")
        
        except Exception as e:
            self.toast_manager.error(f"Ошибка загрузки: {e}")
    
    @asyncSlot(str)
    async def _on_ask_model(self, user_text: str):
        """Handle ask model request"""
        if not user_text.strip():
            self.toast_manager.warning("Пустое сообщение")
            return
        
        if not self.agent:
            self.toast_manager.error("Агент не инициализирован. Нажмите 'Подключиться'.")
            return
        
        if not self.current_conversation_id:
            self.toast_manager.warning("Нет активного разговора")
            return
        
        # Disable input while processing
        if self.chat_panel:
            self.chat_panel.set_input_enabled(False)
            self.chat_panel.add_user_message(user_text)
        
        self.toast_manager.info("Отправка запроса модели...")
        
        try:
            # Collect file URIs from attached gemini files
            file_uris = [gf["gemini_uri"] for gf in self.attached_gemini_files]
            
            # Ask agent
            reply = await self.agent.ask(
                conversation_id=self.current_conversation_id,
                user_text=user_text,
                file_uris=file_uris,
            )
            
            # Display assistant response
            if self.chat_panel:
                meta = {
                    "model": self.agent.default_model,
                    "thinking_level": "low",
                    "is_final": reply.is_final,
                    "actions": [
                        {"type": a.type, "payload": a.payload, "note": a.note}
                        for a in reply.actions
                    ]
                }
                self.chat_panel.add_assistant_message(reply.assistant_text, meta)
                
                # Process actions
                await self._process_model_actions(reply.actions)
            
            self.toast_manager.success("Ответ получен")
        
        except Exception as e:
            self.toast_manager.error(f"Ошибка запроса: {e}")
            if self.chat_panel:
                self.chat_panel.add_system_message(f"Ошибка: {e}", "error")
        
        finally:
            # Re-enable input
            if self.chat_panel:
                self.chat_panel.set_input_enabled(True)
    
    async def _process_model_actions(self, actions: list):
        """Process model actions"""
        for action in actions:
            if action.type == "open_image":
                await self._handle_open_image_action(action)
            elif action.type == "request_roi":
                await self._handle_request_roi_action(action)
            elif action.type == "final":
                if self.chat_panel:
                    self.chat_panel.add_system_message("Диалог завершён", "success")
    
    async def _handle_open_image_action(self, action):
        """Handle open_image action from model"""
        self.toast_manager.info("Открытие изображения...")
        
        try:
            # Get file reference from payload
            context_item_id = action.payload.get("context_item_id")
            r2_key = action.payload.get("r2_key")
            
            # Find context item
            context_item = None
            if context_item_id and self.right_panel:
                for item in self.right_panel.context_items:
                    if item.id == context_item_id:
                        context_item = item
                        break
            
            if not context_item and r2_key:
                # Create temporary context item
                from app.models.schemas import ContextItem
                context_item = ContextItem(
                    id=hashlib.md5(r2_key.encode()).hexdigest(),
                    title=r2_key.split("/")[-1],
                    r2_key=r2_key,
                    mime_type="application/pdf",
                    status="local"
                )
            
            if not context_item or not context_item.r2_key:
                self.toast_manager.warning("Не удается найти ссылку на файл")
                return
            
            await self._open_image_viewer(context_item, [action])
        
        except Exception as e:
            self.toast_manager.error(f"Ошибка открытия изображения: {e}")
    
    async def _handle_request_roi_action(self, action):
        """Handle request_roi action from model"""
        self.toast_manager.info("Модель запрашивает выбор области...")
        
        try:
            # Get file reference
            image_ref = action.payload.get("image_ref") or action.payload.get("context_item_id")
            
            if not image_ref:
                self.toast_manager.warning("Нет ссылки на изображение в запросе")
                return
            
            # Find context item
            context_item = None
            if self.right_panel:
                for item in self.right_panel.context_items:
                    if item.id == image_ref:
                        context_item = item
                        break
            
            if not context_item:
                self.toast_manager.warning(f"Не удается найти элемент контекста: {image_ref}")
                return
            
            await self._open_image_viewer(context_item, [action])
        
        except Exception as e:
            self.toast_manager.error(f"Ошибка обработки запроса области: {e}")
    
    async def _open_image_viewer(self, context_item, model_actions: list):
        """Open image viewer dialog with ROI selection"""
        if not self.r2_client:
            self.toast_manager.error("R2 клиент не инициализирован")
            return
        
        try:
            # Download file from R2
            self.toast_manager.info("Загрузка файла...")
            url = self.r2_client.build_public_url(context_item.r2_key)
            cached_path = await self.r2_client.download_to_cache(url, context_item.id)
            
            # Render preview
            self.toast_manager.info("Создание превью...")
            preview_image = self.pdf_renderer.render_preview(cached_path, page_num=0, dpi=150)
            
            # Create and show dialog
            dialog = ImageViewerDialog(self)
            dialog.load_image(preview_image)
            dialog.set_model_suggestions(model_actions)
            
            # Connect signals
            dialog.roiSelected.connect(
                lambda bbox, note: asyncio.create_task(
                    self._on_roi_selected(context_item, cached_path, bbox, note)
                )
            )
            dialog.roiRejected.connect(self._on_roi_rejected)
            
            # Show dialog (non-blocking)
            dialog.exec()
        
        except Exception as e:
            self.toast_manager.error(f"Ошибка открытия просмотра изображения: {e}")
    
    async def _on_roi_selected(self, context_item, pdf_path: Path, bbox_norm: tuple, user_note: str):
        """Handle ROI selection"""
        self.toast_manager.info("Обработка выделенной области...")
        
        try:
            # Render ROI with high quality
            self.toast_manager.info("Создание области в высоком разрешении...")
            roi_png_bytes = self.pdf_renderer.render_roi(
                pdf_path,
                bbox_norm,
                page_num=0,
                dpi=400
            )
            
            # Generate R2 key for artifact
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            roi_filename = f"roi_{timestamp}.png"
            r2_key = f"artifacts/{self.current_conversation_id}/{roi_filename}"
            
            # Upload to R2
            if self.r2_client:
                self.toast_manager.info("Загрузка области в R2...")
                await self.r2_client.upload_bytes(
                    r2_key,
                    roi_png_bytes,
                    content_type="image/png"
                )
                
                # Save artifact metadata
                if self.supabase_repo and self.current_conversation_id:
                    await self.supabase_repo.qa_add_artifact(
                        conversation_id=str(self.current_conversation_id),
                        artifact_type="roi_png",
                        r2_key=r2_key,
                        file_name=roi_filename,
                        mime_type="image/png",
                        file_size=len(roi_png_bytes),
                        metadata={
                            "bbox_norm": list(bbox_norm),
                            "user_note": user_note,
                            "source_context_item_id": context_item.id,
                        }
                    )
            
            # Upload ROI to Gemini Files
            if self.gemini_client:
                self.toast_manager.info("Загрузка области в Gemini Files...")
                
                # Save bytes to temp file
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    tmp.write(roi_png_bytes)
                    tmp_path = Path(tmp.name)
                
                try:
                    result = await self.gemini_client.upload_file(
                        tmp_path,
                        mime_type="image/png",
                        display_name=f"Область: {roi_filename}"
                    )
                    
                    gemini_uri = result["uri"]
                    
                    # Ask model again with ROI
                    roi_context = f"Пользователь выделил область на документе. Примечание: {user_note or 'нет'}"
                    
                    if self.chat_panel:
                        self.chat_panel.add_system_message(
                            f"ROI выделен и загружен. Отправка модели...",
                            "success"
                        )
                        self.chat_panel.set_input_enabled(False)
                    
                    # Include ROI in file_uris for next request
                    file_uris = [gf["gemini_uri"] for gf in self.attached_gemini_files]
                    file_uris.append(gemini_uri)
                    
                    reply = await self.agent.ask(
                        conversation_id=self.current_conversation_id,
                        user_text=roi_context,
                        file_uris=file_uris,
                    )
                    
                    # Display response
                    if self.chat_panel:
                        meta = {
                            "model": self.agent.default_model,
                            "thinking_level": "low",
                            "is_final": reply.is_final,
                            "actions": [
                                {"type": a.type, "payload": a.payload, "note": a.note}
                                for a in reply.actions
                            ]
                        }
                        self.chat_panel.add_assistant_message(reply.assistant_text, meta)
                        self.chat_panel.set_input_enabled(True)
                    
                    self.toast_manager.success("Область обработана успешно")
                
                finally:
                    # Clean up temp file
                    if tmp_path.exists():
                        tmp_path.unlink()
        
        except Exception as e:
            self.toast_manager.error(f"Ошибка обработки области: {e}")
            if self.chat_panel:
                self.chat_panel.set_input_enabled(True)
    
    def _on_roi_rejected(self, reason: str):
        """Handle ROI rejection"""
        self.toast_manager.info(f"Область отклонена: {reason}")
