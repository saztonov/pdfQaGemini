"""Application entry point"""
import sys
import os
import asyncio
import logging
import shutil
from pathlib import Path
from logging.handlers import RotatingFileHandler
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QDir
import qasync
from app.ui.main_window import MainWindow


def clear_cache():
    """Clear Python and Qt caches on startup"""
    # Disable Python bytecode cache
    sys.dont_write_bytecode = True
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

    # Clear __pycache__ directories in app folder
    app_dir = Path(__file__).parent
    for pycache in app_dir.rglob("__pycache__"):
        try:
            shutil.rmtree(pycache)
        except Exception:
            pass

    # Clear Qt cache directory
    qt_cache = Path(QDir.tempPath()) / "pdfQaGemini"
    if qt_cache.exists():
        try:
            shutil.rmtree(qt_cache)
        except Exception:
            pass


def setup_logging():
    """Настройка логирования с записью в файл"""
    # Create logs directory
    logs_dir = Path(__file__).parent.parent.parent / "logs"
    logs_dir.mkdir(exist_ok=True)
    log_file = logs_dir / "desktop.log"

    # Configure handlers
    handlers = [
        logging.StreamHandler(sys.stdout),
        RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding="utf-8",
        ),
    ]

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=handlers,
    )

    # Suppress verbose realtime and httpx logs
    logging.getLogger("realtime._async.client").setLevel(logging.WARNING)
    logging.getLogger("realtime._async.channel").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    logger = logging.getLogger(__name__)
    logger.info("=== ЗАПУСК ПРИЛОЖЕНИЯ pdfQaGemini ===")
    logger.info(f"Логи сохраняются в: {log_file}")


def main():
    """Main entry point with qasync integration"""
    clear_cache()
    setup_logging()

    app = QApplication(sys.argv)
    app.setApplicationName("pdfQaGemini")

    # Create async event loop
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    # Create main window
    window = MainWindow()
    window.show()

    # Run async event loop
    with loop:
        loop.run_forever()


if __name__ == "__main__":
    main()
