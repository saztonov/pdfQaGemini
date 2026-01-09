"""
Миксин для настройки меню и тулбара
По образцу архитектуры из test/menu_setup.py
"""

from typing import TYPE_CHECKING

from PySide6.QtGui import QAction

if TYPE_CHECKING:
    from app.ui.main_window import MainWindow


# Общие стили для меню (темная тема)
MENU_STYLE = """
    QMenuBar {
        background-color: #1e1e1e;
        color: #cccccc;
        border-bottom: 1px solid #3e3e42;
        padding: 2px 0px;
    }
    QMenuBar::item {
        background-color: transparent;
        padding: 6px 12px;
        margin: 0px;
    }
    QMenuBar::item:selected {
        background-color: #094771;
        color: #ffffff;
    }
    QMenuBar::item:pressed {
        background-color: #0e639c;
    }
    QMenu {
        background-color: #252526;
        color: #cccccc;
        border: 1px solid #3e3e42;
        padding: 4px 0px;
    }
    QMenu::item {
        padding: 8px 32px 8px 12px;
        margin: 0px;
    }
    QMenu::item:selected {
        background-color: #094771;
        color: #ffffff;
    }
    QMenu::separator {
        height: 1px;
        background-color: #3e3e42;
        margin: 4px 8px;
    }
    QMenu::icon {
        margin-left: 8px;
    }
"""

# Стили для контекстного меню
CONTEXT_MENU_STYLE = """
    QMenu {
        background-color: #252526;
        color: #cccccc;
        border: 1px solid #3e3e42;
        padding: 4px 0px;
    }
    QMenu::item {
        padding: 8px 24px 8px 12px;
        margin: 0px;
    }
    QMenu::item:selected {
        background-color: #094771;
        color: #ffffff;
    }
    QMenu::separator {
        height: 1px;
        background-color: #3e3e42;
        margin: 4px 8px;
    }
"""


class MenuSetupMixin:
    """Миксин для создания меню и тулбара"""

    def _setup_menu(self: "MainWindow"):
        """Настройка главного меню"""
        menubar = self.menuBar()
        menubar.setStyleSheet(MENU_STYLE)

        self._setup_file_menu(menubar)
        self._setup_view_menu(menubar)
        self._setup_settings_menu(menubar)

    def _setup_file_menu(self: "MainWindow", menubar):
        """Настройка меню 'Файл'"""
        file_menu = menubar.addMenu("📁 Файл")

        self.action_upload = QAction("📤  Загрузить в Gemini", self)
        self.action_upload.setShortcut("Ctrl+U")
        self.action_upload.setToolTip("Загрузить выбранные файлы в Gemini Files")
        self.action_upload.triggered.connect(self._on_upload_selected)
        self.action_upload.setEnabled(False)
        file_menu.addAction(self.action_upload)

        file_menu.addSeparator()

        action_exit = QAction("🚪  Выход", self)
        action_exit.setShortcut("Alt+F4")
        action_exit.triggered.connect(self.close)
        file_menu.addAction(action_exit)

    def _setup_view_menu(self: "MainWindow", menubar):
        """Setup View menu with dock panel actions"""
        view_menu = menubar.addMenu("View")

        self.action_refresh_tree = QAction("Refresh Projects Tree", self)
        self.action_refresh_tree.setShortcut("Ctrl+R")
        self.action_refresh_tree.setToolTip("Refresh projects tree")
        self.action_refresh_tree.triggered.connect(self._on_refresh_tree)
        self.action_refresh_tree.setEnabled(False)
        view_menu.addAction(self.action_refresh_tree)

        self.action_refresh_gemini = QAction("Refresh Gemini Files", self)
        self.action_refresh_gemini.setShortcut("Ctrl+Shift+R")
        self.action_refresh_gemini.setToolTip("Refresh Gemini Files list")
        self.action_refresh_gemini.triggered.connect(self._on_refresh_gemini)
        self.action_refresh_gemini.setEnabled(False)
        view_menu.addAction(self.action_refresh_gemini)

        view_menu.addSeparator()

        self.action_model_inspector = QAction("Model Inspector Window", self)
        self.action_model_inspector.setShortcut("Ctrl+I")
        self.action_model_inspector.setToolTip(
            "Open separate model inspector window with full logs"
        )
        self.action_model_inspector.triggered.connect(self._on_open_inspector)
        view_menu.addAction(self.action_model_inspector)

        view_menu.addSeparator()

        # Panels submenu - uses dock.toggleViewAction() for automatic sync
        panels_menu = view_menu.addMenu("Panels")

        # Note: Dock toggle actions will be added after docks are created
        # Store menu reference for later use
        self._panels_menu = panels_menu

    def _setup_dock_menu_actions(self: "MainWindow"):
        """Setup dock toggle actions in Panels menu (called after docks are created)"""
        if not hasattr(self, "_panels_menu"):
            return

        # Get toggle actions from docks (automatically synced with visibility)
        if self.projects_dock:
            action = self.projects_dock.toggleViewAction()
            action.setText("Projects Panel")
            action.setShortcut("Ctrl+1")
            self._panels_menu.addAction(action)

        if self.chats_dock:
            action = self.chats_dock.toggleViewAction()
            action.setText("Chats Panel")
            action.setShortcut("Ctrl+2")
            self._panels_menu.addAction(action)

        if self.inspector_dock:
            action = self.inspector_dock.toggleViewAction()
            action.setText("Inspector Panel")
            action.setShortcut("Ctrl+3")
            self._panels_menu.addAction(action)

        self._panels_menu.addSeparator()

        # Reset layout action
        self.action_reset_layout = QAction("Reset Layout", self)
        self.action_reset_layout.setToolTip("Reset panels to default layout")
        self.action_reset_layout.triggered.connect(self._reset_dock_layout)
        self._panels_menu.addAction(self.action_reset_layout)

    def _setup_settings_menu(self: "MainWindow", menubar):
        """Настройка меню 'Настройки'"""
        settings_menu = menubar.addMenu("⚙️ Настройки")

        self.action_settings = QAction("🔌  Настройки подключения", self)
        self.action_settings.setShortcut("Ctrl+,")
        self.action_settings.setToolTip("Настройки подключения")
        self.action_settings.triggered.connect(self._on_open_settings)
        settings_menu.addAction(self.action_settings)

        settings_menu.addSeparator()

        self.action_prompts = QAction("📝  Промты", self)
        self.action_prompts.setShortcut("Ctrl+P")
        self.action_prompts.setToolTip("Управление промтами")
        self.action_prompts.triggered.connect(self._on_open_prompts)
        self.action_prompts.setEnabled(False)
        settings_menu.addAction(self.action_prompts)
