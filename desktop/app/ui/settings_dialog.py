"""Settings dialog - with remote settings from Supabase"""

import asyncio
import logging
from typing import Optional, Callable

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QGroupBox,
    QLabel,
    QSpinBox,
    QTabWidget,
    QWidget,
    QMessageBox,
)
from PySide6.QtCore import QSettings, Signal

logger = logging.getLogger(__name__)


class SettingsDialog(QDialog):
    """Settings configuration dialog with local and remote settings"""

    # Signal emitted when remote settings are saved successfully
    remote_settings_saved = Signal()

    def __init__(self, parent=None, api_client=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки")
        self.resize(550, 500)

        self.settings = QSettings("pdfQaGemini", "Desktop")
        self.api_client = api_client
        self._remote_settings: dict = {}

        self._setup_ui()
        self._load_local_settings()

    def set_api_client(self, api_client):
        """Set API client for remote settings operations"""
        self.api_client = api_client
        self._update_remote_tab_state()

    def _setup_ui(self):
        """Initialize UI with tabs"""
        layout = QVBoxLayout(self)

        # Tab widget
        self.tabs = QTabWidget()

        # Tab 1: Connection settings
        self.connection_tab = QWidget()
        self._setup_connection_tab()
        self.tabs.addTab(self.connection_tab, "Подключение")

        # Tab 2: Local settings
        self.local_tab = QWidget()
        self._setup_local_tab()
        self.tabs.addTab(self.local_tab, "Локальные")

        # Tab 3: Remote settings (server/Supabase)
        self.remote_tab = QWidget()
        self._setup_remote_tab()
        self.tabs.addTab(self.remote_tab, "Серверные")

        layout.addWidget(self.tabs)

        # Buttons
        button_layout = QHBoxLayout()

        self.btn_save = QPushButton("Сохранить")
        self.btn_save.clicked.connect(self._save_all_settings)
        self.btn_save.setDefault(True)

        self.btn_cancel = QPushButton("Отмена")
        self.btn_cancel.clicked.connect(self.reject)

        button_layout.addStretch()
        button_layout.addWidget(self.btn_save)
        button_layout.addWidget(self.btn_cancel)

        layout.addLayout(button_layout)

    def _setup_connection_tab(self):
        """Setup connection settings tab"""
        layout = QVBoxLayout(self.connection_tab)

        # Server connection group
        server_group = QGroupBox("Подключение к серверу")
        server_form = QFormLayout(server_group)

        self.server_url_edit = QLineEdit()
        self.server_url_edit.setPlaceholderText("http://localhost:8000")
        server_form.addRow("URL сервера:", self.server_url_edit)

        self.api_token_edit = QLineEdit()
        self.api_token_edit.setPlaceholderText("xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx")
        self.api_token_edit.setEchoMode(QLineEdit.Password)
        server_form.addRow("API токен:", self.api_token_edit)

        # Info label
        info = QLabel(
            "API токен выдается администратором сервера.\n"
            "После подключения доступны серверные настройки на вкладке 'Серверные'."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #666; font-size: 11px; padding: 10px 5px;")
        server_form.addRow(info)

        layout.addWidget(server_group)
        layout.addStretch()

    def _setup_local_tab(self):
        """Setup local settings tab"""
        layout = QVBoxLayout(self.local_tab)

        # Local settings group
        local_group = QGroupBox("Локальные настройки")
        local_form = QFormLayout(local_group)

        self.cache_dir_edit = QLineEdit()
        self.cache_dir_edit.setPlaceholderText("./cache")
        local_form.addRow("Папка кэша:", self.cache_dir_edit)

        self.cache_size_edit = QLineEdit()
        self.cache_size_edit.setPlaceholderText("500")
        local_form.addRow("Размер кэша (МБ):", self.cache_size_edit)

        layout.addWidget(local_group)
        layout.addStretch()

    def _setup_remote_tab(self):
        """Setup remote settings tab (loaded from server)"""
        layout = QVBoxLayout(self.remote_tab)

        # Status and refresh button
        status_layout = QHBoxLayout()

        self.remote_status_label = QLabel("Не подключено к серверу")
        self.remote_status_label.setStyleSheet("color: #888;")
        status_layout.addWidget(self.remote_status_label)

        status_layout.addStretch()

        self.btn_refresh = QPushButton("Обновить")
        self.btn_refresh.clicked.connect(self._load_remote_settings)
        self.btn_refresh.setEnabled(False)
        status_layout.addWidget(self.btn_refresh)

        layout.addLayout(status_layout)

        # Gemini API settings
        gemini_group = QGroupBox("Gemini API")
        gemini_form = QFormLayout(gemini_group)

        self.gemini_api_key_edit = QLineEdit()
        self.gemini_api_key_edit.setEchoMode(QLineEdit.Password)
        self.gemini_api_key_edit.setPlaceholderText("API ключ Google Gemini")
        gemini_form.addRow("API ключ:", self.gemini_api_key_edit)

        self.default_model_edit = QLineEdit()
        self.default_model_edit.setPlaceholderText("gemini-3-flash-preview")
        gemini_form.addRow("Модель по умолчанию:", self.default_model_edit)

        layout.addWidget(gemini_group)

        # Chat settings
        chat_group = QGroupBox("Настройки чата")
        chat_form = QFormLayout(chat_group)

        self.max_history_pairs_spin = QSpinBox()
        self.max_history_pairs_spin.setRange(0, 50)
        self.max_history_pairs_spin.setValue(5)
        self.max_history_pairs_spin.setToolTip(
            "Количество предыдущих пар вопрос/ответ, передаваемых модели для контекста.\n"
            "0 = без истории (каждый вопрос независимый)"
        )
        chat_form.addRow("История чата (пар Q&A):", self.max_history_pairs_spin)

        chat_info = QLabel(
            "Модель будет учитывать указанное количество предыдущих\n"
            "вопросов и ответов для понимания контекста разговора."
        )
        chat_info.setWordWrap(True)
        chat_info.setStyleSheet("color: #666; font-size: 11px; padding: 5px;")
        chat_form.addRow(chat_info)

        layout.addWidget(chat_group)

        # R2 Storage settings
        r2_group = QGroupBox("Cloudflare R2 Storage")
        r2_form = QFormLayout(r2_group)

        self.r2_account_id_edit = QLineEdit()
        self.r2_account_id_edit.setPlaceholderText("Account ID")
        r2_form.addRow("Account ID:", self.r2_account_id_edit)

        self.r2_access_key_edit = QLineEdit()
        self.r2_access_key_edit.setEchoMode(QLineEdit.Password)
        self.r2_access_key_edit.setPlaceholderText("Access Key ID")
        r2_form.addRow("Access Key:", self.r2_access_key_edit)

        self.r2_secret_key_edit = QLineEdit()
        self.r2_secret_key_edit.setEchoMode(QLineEdit.Password)
        self.r2_secret_key_edit.setPlaceholderText("Secret Access Key")
        r2_form.addRow("Secret Key:", self.r2_secret_key_edit)

        self.r2_bucket_edit = QLineEdit()
        self.r2_bucket_edit.setPlaceholderText("bucket-name")
        r2_form.addRow("Bucket:", self.r2_bucket_edit)

        self.r2_public_url_edit = QLineEdit()
        self.r2_public_url_edit.setPlaceholderText("https://pub-xxx.r2.dev")
        r2_form.addRow("Public URL:", self.r2_public_url_edit)

        layout.addWidget(r2_group)

        # Worker settings
        worker_group = QGroupBox("Настройки воркера")
        worker_form = QFormLayout(worker_group)

        self.worker_max_jobs_spin = QSpinBox()
        self.worker_max_jobs_spin.setRange(1, 100)
        self.worker_max_jobs_spin.setValue(10)
        worker_form.addRow("Макс. параллельных задач:", self.worker_max_jobs_spin)

        self.worker_timeout_spin = QSpinBox()
        self.worker_timeout_spin.setRange(30, 3600)
        self.worker_timeout_spin.setValue(300)
        self.worker_timeout_spin.setSuffix(" сек")
        worker_form.addRow("Таймаут задачи:", self.worker_timeout_spin)

        self.worker_retries_spin = QSpinBox()
        self.worker_retries_spin.setRange(0, 10)
        self.worker_retries_spin.setValue(3)
        worker_form.addRow("Макс. повторов:", self.worker_retries_spin)

        layout.addWidget(worker_group)

        layout.addStretch()

        # Initially disable all remote controls
        self._set_remote_controls_enabled(False)

    def _set_remote_controls_enabled(self, enabled: bool):
        """Enable/disable all remote settings controls"""
        controls = [
            self.gemini_api_key_edit,
            self.default_model_edit,
            self.max_history_pairs_spin,
            self.r2_account_id_edit,
            self.r2_access_key_edit,
            self.r2_secret_key_edit,
            self.r2_bucket_edit,
            self.r2_public_url_edit,
            self.worker_max_jobs_spin,
            self.worker_timeout_spin,
            self.worker_retries_spin,
        ]
        for ctrl in controls:
            ctrl.setEnabled(enabled)

    def _update_remote_tab_state(self):
        """Update remote tab based on connection state"""
        if self.api_client:
            self.remote_status_label.setText("Подключено к серверу")
            self.remote_status_label.setStyleSheet("color: #2a2;")
            self.btn_refresh.setEnabled(True)
            self._set_remote_controls_enabled(True)
        else:
            self.remote_status_label.setText("Не подключено к серверу")
            self.remote_status_label.setStyleSheet("color: #888;")
            self.btn_refresh.setEnabled(False)
            self._set_remote_controls_enabled(False)

    def _load_local_settings(self):
        """Load settings from QSettings"""
        self.server_url_edit.setText(self.settings.value("server/url", ""))
        self.api_token_edit.setText(self.settings.value("server/api_token", ""))
        self.cache_dir_edit.setText(self.settings.value("general/cache_dir", "./cache"))
        self.cache_size_edit.setText(self.settings.value("general/cache_size_mb", "500"))

    def _load_remote_settings(self):
        """Load settings from server (async)"""
        if not self.api_client:
            return

        # Run async operation
        try:
            loop = asyncio.get_event_loop()
            loop.create_task(self._do_load_remote_settings())
        except RuntimeError:
            logger.warning("No event loop available for loading remote settings")

    async def _do_load_remote_settings(self):
        """Actually load remote settings"""
        try:
            self.remote_status_label.setText("Загрузка...")
            self._remote_settings = await self.api_client.get_settings()
            self._populate_remote_fields()
            self.remote_status_label.setText("Настройки загружены")
            self.remote_status_label.setStyleSheet("color: #2a2;")
            logger.info("Remote settings loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load remote settings: {e}")
            self.remote_status_label.setText(f"Ошибка: {e}")
            self.remote_status_label.setStyleSheet("color: #a22;")

    def _populate_remote_fields(self):
        """Populate remote fields with loaded settings"""
        s = self._remote_settings

        # Gemini
        self.gemini_api_key_edit.setText(s.get("gemini_api_key", ""))
        self.default_model_edit.setText(s.get("default_model", "gemini-3-flash-preview"))

        # Chat
        self.max_history_pairs_spin.setValue(int(s.get("max_history_pairs", 5)))

        # R2
        self.r2_account_id_edit.setText(s.get("r2_account_id", ""))
        self.r2_access_key_edit.setText(s.get("r2_access_key_id", ""))
        self.r2_secret_key_edit.setText(s.get("r2_secret_access_key", ""))
        self.r2_bucket_edit.setText(s.get("r2_bucket_name", ""))
        self.r2_public_url_edit.setText(s.get("r2_public_url", ""))

        # Worker
        self.worker_max_jobs_spin.setValue(int(s.get("worker_max_jobs", 10)))
        self.worker_timeout_spin.setValue(int(s.get("worker_job_timeout", 300)))
        self.worker_retries_spin.setValue(int(s.get("worker_max_retries", 3)))

    def _save_all_settings(self):
        """Save both local and remote settings"""
        # Save local settings
        self._save_local_settings()

        # Save remote settings if connected
        if self.api_client:
            try:
                loop = asyncio.get_event_loop()
                loop.create_task(self._do_save_remote_settings())
            except RuntimeError:
                logger.warning("No event loop for saving remote settings")
                self.accept()
        else:
            self.accept()

    def _save_local_settings(self):
        """Save local settings to QSettings"""
        self.settings.setValue("server/url", self.server_url_edit.text().strip())
        self.settings.setValue("server/api_token", self.api_token_edit.text().strip())
        self.settings.setValue("general/cache_dir", self.cache_dir_edit.text().strip())
        self.settings.setValue("general/cache_size_mb", self.cache_size_edit.text().strip())
        self.settings.sync()

    def _is_masked(self, value: str) -> bool:
        """Check if value is a masked placeholder (contains ***)"""
        return "***" in value if value else False

    async def _do_save_remote_settings(self):
        """Save remote settings to server"""
        try:
            # Collect changed settings
            new_settings = {}

            # Only include non-masked values (don't overwrite with masked values)
            # Masked values look like "AIza***xyz9" (first 4 + *** + last 4)
            gemini_key = self.gemini_api_key_edit.text()
            if gemini_key and not self._is_masked(gemini_key):
                new_settings["gemini_api_key"] = gemini_key

            new_settings["default_model"] = self.default_model_edit.text()
            new_settings["max_history_pairs"] = self.max_history_pairs_spin.value()

            new_settings["r2_account_id"] = self.r2_account_id_edit.text()

            r2_access = self.r2_access_key_edit.text()
            if r2_access and not self._is_masked(r2_access):
                new_settings["r2_access_key_id"] = r2_access

            r2_secret = self.r2_secret_key_edit.text()
            if r2_secret and not self._is_masked(r2_secret):
                new_settings["r2_secret_access_key"] = r2_secret

            new_settings["r2_bucket_name"] = self.r2_bucket_edit.text()
            new_settings["r2_public_url"] = self.r2_public_url_edit.text()

            new_settings["worker_max_jobs"] = self.worker_max_jobs_spin.value()
            new_settings["worker_job_timeout"] = self.worker_timeout_spin.value()
            new_settings["worker_max_retries"] = self.worker_retries_spin.value()

            updated = await self.api_client.update_settings_batch(new_settings)
            logger.info(f"Remote settings saved: {updated} updated")

            self.remote_settings_saved.emit()
            self.accept()

        except Exception as e:
            logger.error(f"Failed to save remote settings: {e}")
            QMessageBox.warning(
                self,
                "Ошибка сохранения",
                f"Не удалось сохранить серверные настройки:\n{e}",
            )

    def load_remote_settings_sync(self, settings: dict):
        """Load remote settings synchronously (called from outside)"""
        self._remote_settings = settings
        self._populate_remote_fields()
        self._update_remote_tab_state()

    @staticmethod
    def get_settings() -> dict:
        """Get current local settings as dict"""
        settings = QSettings("pdfQaGemini", "Desktop")

        return {
            "server_url": settings.value("server/url", ""),
            "api_token": settings.value("server/api_token", ""),
            "cache_dir": settings.value("general/cache_dir", "./cache"),
            "cache_size_mb": int(settings.value("general/cache_size_mb", "500") or "500"),
        }

    @staticmethod
    def is_configured() -> bool:
        """Check if essential settings are configured"""
        settings = SettingsDialog.get_settings()
        return bool(settings["server_url"] and settings["api_token"])

    @staticmethod
    def save_server_config(config: dict) -> None:
        """Save server config received from API"""
        settings = QSettings("pdfQaGemini", "Desktop")
        settings.setValue("server_config/client_id", config.get("client_id", "default"))
        settings.setValue("server_config/supabase_url", config.get("supabase_url", ""))
        settings.setValue("server_config/supabase_key", config.get("supabase_key", ""))
        settings.setValue("server_config/r2_public_base_url", config.get("r2_public_base_url", ""))
        settings.setValue(
            "server_config/default_model", config.get("default_model", "gemini-2.0-flash")
        )
        settings.setValue(
            "server_config/max_history_pairs", config.get("max_history_pairs", 5)
        )
        settings.sync()

    @staticmethod
    def get_server_config() -> dict:
        """Get cached server config"""
        settings = QSettings("pdfQaGemini", "Desktop")
        return {
            "client_id": settings.value("server_config/client_id", "default"),
            "supabase_url": settings.value("server_config/supabase_url", ""),
            "supabase_key": settings.value("server_config/supabase_key", ""),
            "r2_public_base_url": settings.value("server_config/r2_public_base_url", ""),
            "default_model": settings.value("server_config/default_model", "gemini-2.0-flash"),
            "max_history_pairs": int(settings.value("server_config/max_history_pairs", 5)),
        }

    @staticmethod
    def clear_server_config() -> None:
        """Clear cached server config (on disconnect)"""
        settings = QSettings("pdfQaGemini", "Desktop")
        settings.remove("server_config")
        settings.sync()
