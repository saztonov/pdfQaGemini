"""Settings dialog - simplified for centralized config"""

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QGroupBox,
    QLabel,
)
from PySide6.QtCore import QSettings


class SettingsDialog(QDialog):
    """Settings configuration dialog - server connection only"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки подключения")
        self.resize(500, 300)

        self.settings = QSettings("pdfQaGemini", "Desktop")

        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        """Initialize UI"""
        layout = QVBoxLayout(self)

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
            "Все остальные настройки (Supabase, Gemini, R2) хранятся на сервере."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #666; font-size: 11px; padding: 10px 5px;")
        server_form.addRow(info)

        layout.addWidget(server_group)

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

    def _load_settings(self):
        """Load settings from QSettings"""
        self.server_url_edit.setText(self.settings.value("server/url", ""))
        self.api_token_edit.setText(self.settings.value("server/api_token", ""))
        self.cache_dir_edit.setText(self.settings.value("general/cache_dir", "./cache"))
        self.cache_size_edit.setText(self.settings.value("general/cache_size_mb", "500"))

    def _save_settings(self):
        """Save settings to QSettings"""
        self.settings.setValue("server/url", self.server_url_edit.text().strip())
        self.settings.setValue("server/api_token", self.api_token_edit.text().strip())
        self.settings.setValue("general/cache_dir", self.cache_dir_edit.text().strip())
        self.settings.setValue("general/cache_size_mb", self.cache_size_edit.text().strip())

        self.settings.sync()
        self.accept()

    @staticmethod
    def get_settings() -> dict:
        """Get current settings as dict (local settings only)"""
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
        }

    @staticmethod
    def clear_server_config() -> None:
        """Clear cached server config (on disconnect)"""
        settings = QSettings("pdfQaGemini", "Desktop")
        settings.remove("server_config")
        settings.sync()
