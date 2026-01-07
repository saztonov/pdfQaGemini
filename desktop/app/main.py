"""Application entry point"""
import sys
import asyncio
import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler
from PySide6.QtWidgets import QApplication
import qasync
from app.ui.main_window import MainWindow


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
    logger = logging.getLogger(__name__)
    logger.info("=== ЗАПУСК ПРИЛОЖЕНИЯ pdfQaGemini ===")
    logger.info(f"Логи сохраняются в: {log_file}")


def main():
    """Main entry point with qasync integration"""
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
