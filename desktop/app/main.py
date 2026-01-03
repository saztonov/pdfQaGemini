"""Application entry point"""
import sys
import asyncio
import logging
from PySide6.QtWidgets import QApplication
import qasync
from app.ui.main_window import MainWindow


def setup_logging():
    """Настройка логирования"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )
    logger = logging.getLogger(__name__)
    logger.info("=== ЗАПУСК ПРИЛОЖЕНИЯ pdfQaGemini ===")


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
