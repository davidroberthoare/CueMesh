"""CueMesh Client entry point."""
from __future__ import annotations
import asyncio
import logging
import sys
import threading
from pathlib import Path

from PySide6.QtWidgets import QApplication

from client.mpv_controller import MpvController
from client.ui.main_window import ClientMainWindow
from shared.logging_utils import setup_rotating_logger


def _run_asyncio_loop(loop: asyncio.AbstractEventLoop) -> None:
    asyncio.set_event_loop(loop)
    loop.run_forever()


def main() -> None:
    log_dir = Path("logs")
    setup_rotating_logger("cuemesh.client", log_dir)
    logger = logging.getLogger("cuemesh.client")
    logger.info("CueMesh Client starting")

    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=_run_asyncio_loop, args=(loop,), daemon=True)
    thread.start()

    app = QApplication(sys.argv)
    app.setApplicationName("CueMesh Client")
    app.setOrganizationName("CueMesh")

    mpv = MpvController()
    # Start mpv (non-blocking)
    asyncio.run_coroutine_threadsafe(mpv.start(), loop)

    window = ClientMainWindow(loop, mpv)
    window.show()

    exit_code = app.exec()

    # Cleanup
    asyncio.run_coroutine_threadsafe(mpv.stop_subprocess(), loop)
    loop.call_soon_threadsafe(loop.stop)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
