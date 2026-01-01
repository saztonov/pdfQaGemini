"""Test SettingsDialog"""
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QSettings
from app.ui.settings_dialog import SettingsDialog


@pytest.fixture(scope="session")
def qapp():
    """Create QApplication for tests"""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def settings_dialog(qapp):
    """Create SettingsDialog"""
    # Clear settings before test
    settings = QSettings("pdfQaGemini", "Desktop")
    settings.clear()
    
    dialog = SettingsDialog()
    yield dialog
    dialog.deleteLater()
    
    # Clear settings after test
    settings.clear()


class TestSettingsDialog:
    def test_init(self, settings_dialog):
        """Test dialog initialization"""
        assert settings_dialog.windowTitle() == "Settings"
        assert settings_dialog.client_id_edit is not None
        assert settings_dialog.supabase_url_edit is not None
    
    def test_cache_dir_default(self, settings_dialog):
        """Test cache dir default value"""
        assert "./cache" in settings_dialog.cache_dir_edit.placeholderText()
    
    def test_save_settings(self, settings_dialog):
        """Test saving settings"""
        # Set values
        settings_dialog.client_id_edit.setText("test_client")
        settings_dialog.supabase_url_edit.setText("https://test.supabase.co")
        settings_dialog.supabase_key_edit.setText("test_key")
        settings_dialog.gemini_api_key_edit.setText("test_gemini_key")
        
        # Save
        settings_dialog._save_settings()
        
        # Verify saved
        config = SettingsDialog.get_settings()
        assert config["client_id"] == "test_client"
        assert config["supabase_url"] == "https://test.supabase.co"
        assert config["supabase_key"] == "test_key"
        assert config["gemini_api_key"] == "test_gemini_key"
    
    def test_load_settings(self):
        """Test loading existing settings"""
        # Save settings first
        settings = QSettings("pdfQaGemini", "Desktop")
        settings.setValue("general/client_id", "loaded_client")
        settings.setValue("supabase/url", "https://loaded.supabase.co")
        settings.sync()
        
        # Create dialog (should load)
        dialog = SettingsDialog()
        
        assert dialog.client_id_edit.text() == "loaded_client"
        assert dialog.supabase_url_edit.text() == "https://loaded.supabase.co"
        
        dialog.deleteLater()
        settings.clear()
    
    def test_get_settings_empty(self):
        """Test get_settings with empty QSettings"""
        settings = QSettings("pdfQaGemini", "Desktop")
        settings.clear()
        
        config = SettingsDialog.get_settings()
        
        assert config["cache_size_mb"] == 500
        assert config["cache_dir"] == "./cache"
    
    def test_is_configured_false(self):
        """Test is_configured returns False when not configured"""
        settings = QSettings("pdfQaGemini", "Desktop")
        settings.clear()
        
        assert not SettingsDialog.is_configured()
    
    def test_is_configured_true(self):
        """Test is_configured returns True when all required set"""
        settings = QSettings("pdfQaGemini", "Desktop")
        settings.setValue("general/client_id", "test")
        settings.setValue("supabase/url", "https://test.supabase.co")
        settings.setValue("supabase/key", "key")
        settings.setValue("gemini/api_key", "gemini_key")
        settings.sync()
        
        assert SettingsDialog.is_configured()
        
        settings.clear()
    
    def test_password_fields_hidden(self, settings_dialog):
        """Test that sensitive fields use password mode"""
        assert settings_dialog.supabase_key_edit.echoMode() == settings_dialog.supabase_key_edit.Password
        assert settings_dialog.r2_access_key_edit.echoMode() == settings_dialog.r2_access_key_edit.Password
        assert settings_dialog.r2_secret_key_edit.echoMode() == settings_dialog.r2_secret_key_edit.Password
        assert settings_dialog.gemini_api_key_edit.echoMode() == settings_dialog.gemini_api_key_edit.Password
    
    def test_r2_optional_fields(self, settings_dialog):
        """Test R2 fields exist"""
        assert settings_dialog.r2_public_url_edit is not None
        assert settings_dialog.r2_endpoint_edit is not None
        assert settings_dialog.r2_bucket_edit is not None
    
    def test_cache_settings(self, settings_dialog):
        """Test cache configuration fields"""
        assert settings_dialog.cache_dir_edit is not None
        assert settings_dialog.cache_size_edit is not None
        
        # Default values
        assert "./cache" in settings_dialog.cache_dir_edit.text()
        assert "500" in settings_dialog.cache_size_edit.text()
