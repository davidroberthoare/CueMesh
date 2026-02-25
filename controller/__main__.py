"""CueMesh Controller entry point."""
from __future__ import annotations
import asyncio
import logging
import sys
import threading
from pathlib import Path

from PySide6.QtWidgets import QApplication

from controller.app_state import AppState
from controller.server import ControllerServer
from controller.discovery import ControllerDiscovery
from controller.log_aggregator import LogAggregator
from controller.ui.main_window import MainWindow
from shared.logging_utils import setup_rotating_logger


def _run_asyncio_loop(loop: asyncio.AbstractEventLoop) -> None:
    asyncio.set_event_loop(loop)
    loop.run_forever()


def main() -> None:
    # Setup logging
    log_dir = Path("logs")
    setup_rotating_logger("cuemesh.controller", log_dir)
    logger = logging.getLogger("cuemesh.controller")
    logger.info("CueMesh Controller starting")

    # Create asyncio loop in background thread
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=_run_asyncio_loop, args=(loop,), daemon=True)
    thread.start()

    # Create server
    server = ControllerServer()
    log_aggregator = LogAggregator(log_dir)

    # Wire server callbacks to log aggregator
    def on_client_log(session, payload):
        log_aggregator.add_client_log(session.client_id, payload)

    server.on_client_log = on_client_log

    # Start server
    asyncio.run_coroutine_threadsafe(server.start(), loop)

    # Start discovery
    discovery = ControllerDiscovery(server.controller_id, server.port)
    asyncio.run_coroutine_threadsafe(discovery.start(), loop)

    # Create Qt app
    app = QApplication(sys.argv)
    app.setApplicationName("CueMesh Controller")
    app.setOrganizationName("CueMesh")

    state = AppState()
    window = MainWindow(state, server, log_aggregator, loop)
    window.show()

    exit_code = app.exec()

    # Cleanup
    asyncio.run_coroutine_threadsafe(discovery.stop(), loop)
    asyncio.run_coroutine_threadsafe(server.stop(), loop)
    loop.call_soon_threadsafe(loop.stop)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
