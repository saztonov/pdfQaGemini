"""Settings dialog"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QPushButton, QGroupBox, QLabel, QTabWidget, QWidget
)
from PySide6.QtCore import Qt, QSettings


class SettingsDialog(QDialog):
    """Settings configuration dialog"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки")
        self.resize(600, 500)
        
        self.settings = QSettings("pdfQaGemini", "Desktop")
        
        self._setup_ui()
        self._load_settings()
    
    def _setup_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout(self)
        
        # Tab widget
        tabs = QTabWidget()
        
        # Tabs
        tabs.addTab(self._create_general_tab(), "Общие")
        tabs.addTab(self._create_supabase_tab(), "Supabase")
        tabs.addTab(self._create_r2_tab(), "Cloudflare R2")
        tabs.addTab(self._create_gemini_tab(), "Gemini")
        
        layout.addWidget(tabs)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.btn_save = QPushButton("Сохранить")
        self.btn_save.clicked.connect(self._save_settings)
        self.btn_save.setDefault(True)
        
        self.btn_cancel = QPushButton("Отмена")
        self.btn_cancel.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(self.btn_save)
        button_layout.addWidget(self.btn_cancel)
        
        layout.addLayout(button_layout)
    
    def _create_general_tab(self) -> QWidget:
        """Create general settings tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        group = QGroupBox("Общие настройки")
        form = QFormLayout(group)
        
        self.model_edit = QLineEdit()
        self.model_edit.setPlaceholderText("gemini-3-flash-preview")
        form.addRow("Модель по умолчанию:", self.model_edit)
        
        self.cache_dir_edit = QLineEdit()
        self.cache_dir_edit.setPlaceholderText("./cache")
        form.addRow("Папка кэша:", self.cache_dir_edit)
        
        self.cache_size_edit = QLineEdit()
        self.cache_size_edit.setPlaceholderText("500")
        form.addRow("Размер кэша (МБ):", self.cache_size_edit)
        
        layout.addWidget(group)
        layout.addStretch()
        
        return widget
    
    def _create_supabase_tab(self) -> QWidget:
        """Create Supabase settings tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        group = QGroupBox("Конфигурация Supabase")
        form = QFormLayout(group)
        
        self.supabase_url_edit = QLineEdit()
        self.supabase_url_edit.setPlaceholderText("https://ваш-проект.supabase.co")
        form.addRow("URL:", self.supabase_url_edit)
        
        self.supabase_key_edit = QLineEdit()
        self.supabase_key_edit.setPlaceholderText("ваш_supabase_ключ")
        self.supabase_key_edit.setEchoMode(QLineEdit.Password)
        form.addRow("Ключ:", self.supabase_key_edit)
        
        # Info label
        info = QLabel(
            "⚠️ RLS не используется. Используйте сервисный ключ или обеспечьте контроль доступа."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #666; font-size: 11px; padding: 5px;")
        form.addRow(info)
        
        layout.addWidget(group)
        layout.addStretch()
        
        return widget
    
    def _create_r2_tab(self) -> QWidget:
        """Create R2 settings tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        group = QGroupBox("Конфигурация Cloudflare R2")
        form = QFormLayout(group)
        
        self.r2_account_id_edit = QLineEdit()
        self.r2_account_id_edit.setPlaceholderText("account_id")
        form.addRow("Account ID:", self.r2_account_id_edit)
        
        self.r2_access_key_id_edit = QLineEdit()
        self.r2_access_key_id_edit.setPlaceholderText("access_key_id")
        self.r2_access_key_id_edit.setEchoMode(QLineEdit.Password)
        form.addRow("Access Key ID:", self.r2_access_key_id_edit)
        
        self.r2_secret_access_key_edit = QLineEdit()
        self.r2_secret_access_key_edit.setPlaceholderText("secret_access_key")
        self.r2_secret_access_key_edit.setEchoMode(QLineEdit.Password)
        form.addRow("Secret Access Key:", self.r2_secret_access_key_edit)
        
        self.r2_bucket_name_edit = QLineEdit()
        self.r2_bucket_name_edit.setPlaceholderText("bucket-name")
        form.addRow("Bucket Name:", self.r2_bucket_name_edit)
        
        self.r2_public_url_edit = QLineEdit()
        self.r2_public_url_edit.setPlaceholderText("https://pub-xxx.r2.dev")
        form.addRow("Public URL:", self.r2_public_url_edit)
        
        layout.addWidget(group)
        layout.addStretch()
        
        return widget
    
    def _create_gemini_tab(self) -> QWidget:
        """Create Gemini settings tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        group = QGroupBox("Конфигурация Gemini API")
        form = QFormLayout(group)
        
        self.gemini_api_key_edit = QLineEdit()
        self.gemini_api_key_edit.setPlaceholderText("ваш_gemini_api_ключ")
        self.gemini_api_key_edit.setEchoMode(QLineEdit.Password)
        form.addRow("API ключ:", self.gemini_api_key_edit)
        
        # Info label
        info = QLabel(
            "Получите API ключ на: https://aistudio.google.com/apikey"
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #666; font-size: 11px; padding: 5px;")
        form.addRow(info)
        
        layout.addWidget(group)
        layout.addStretch()
        
        return widget
    
    def _load_settings(self):
        """Load settings from QSettings"""
        # General
        self.model_edit.setText(
            self.settings.value("general/model_default", "gemini-3-flash-preview")
        )
        self.cache_dir_edit.setText(self.settings.value("general/cache_dir", "./cache"))
        self.cache_size_edit.setText(self.settings.value("general/cache_size_mb", "500"))
        
        # Supabase
        self.supabase_url_edit.setText(self.settings.value("supabase/url", ""))
        self.supabase_key_edit.setText(self.settings.value("supabase/key", ""))
        
        # R2
        self.r2_account_id_edit.setText(self.settings.value("r2/account_id", ""))
        self.r2_access_key_id_edit.setText(self.settings.value("r2/access_key_id", ""))
        self.r2_secret_access_key_edit.setText(self.settings.value("r2/secret_access_key", ""))
        self.r2_bucket_name_edit.setText(self.settings.value("r2/bucket_name", ""))
        self.r2_public_url_edit.setText(self.settings.value("r2/public_url", ""))
        
        # Gemini
        self.gemini_api_key_edit.setText(self.settings.value("gemini/api_key", ""))
    
    def _save_settings(self):
        """Save settings to QSettings"""
        # General
        self.settings.setValue("general/model_default", self.model_edit.text().strip())
        self.settings.setValue("general/cache_dir", self.cache_dir_edit.text().strip())
        self.settings.setValue("general/cache_size_mb", self.cache_size_edit.text().strip())
        
        # Supabase
        self.settings.setValue("supabase/url", self.supabase_url_edit.text().strip())
        self.settings.setValue("supabase/key", self.supabase_key_edit.text().strip())
        
        # R2
        self.settings.setValue("r2/account_id", self.r2_account_id_edit.text().strip())
        self.settings.setValue("r2/access_key_id", self.r2_access_key_id_edit.text().strip())
        self.settings.setValue("r2/secret_access_key", self.r2_secret_access_key_edit.text().strip())
        self.settings.setValue("r2/bucket_name", self.r2_bucket_name_edit.text().strip())
        self.settings.setValue("r2/public_url", self.r2_public_url_edit.text().strip())
        
        # Gemini
        self.settings.setValue("gemini/api_key", self.gemini_api_key_edit.text().strip())
        
        self.settings.sync()
        self.accept()
    
    @staticmethod
    def get_settings() -> dict:
        """Get current settings as dict"""
        settings = QSettings("pdfQaGemini", "Desktop")
        
        account_id = settings.value("r2/account_id", "")
        r2_endpoint = f"https://{account_id}.r2.cloudflarestorage.com" if account_id else ""
        
        return {
            "model_default": settings.value("general/model_default", "gemini-3-flash-preview"),
            "cache_dir": settings.value("general/cache_dir", "./cache"),
            "cache_size_mb": int(settings.value("general/cache_size_mb", "500")),
            "supabase_url": settings.value("supabase/url", ""),
            "supabase_key": settings.value("supabase/key", ""),
            "r2_public_base_url": settings.value("r2/public_url", ""),
            "r2_endpoint": r2_endpoint,
            "r2_bucket": settings.value("r2/bucket_name", ""),
            "r2_access_key": settings.value("r2/access_key_id", ""),
            "r2_secret_key": settings.value("r2/secret_access_key", ""),
            "gemini_api_key": settings.value("gemini/api_key", ""),
        }
    
    @staticmethod
    def is_configured() -> bool:
        """Check if essential settings are configured"""
        settings = SettingsDialog.get_settings()
        
        required = [
            settings["supabase_url"],
            settings["supabase_key"],
            settings["gemini_api_key"],
        ]
        
        return all(required)
