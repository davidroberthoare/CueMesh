"""CueMesh controller discovery via mDNS/zeroconf."""
from __future__ import annotations
import asyncio
import logging
import socket
from typing import Optional

try:
    from zeroconf import ServiceInfo, Zeroconf
    from zeroconf.asyncio import AsyncZeroconf
    ZEROCONF_AVAILABLE = True
except ImportError:
    ZEROCONF_AVAILABLE = False

logger = logging.getLogger("cuemesh.controller.discovery")

SERVICE_TYPE = "_cuemesh._tcp.local."


class ControllerDiscovery:
    """Advertises the controller via mDNS so clients can find it."""

    def __init__(self, controller_id: str, port: int, show_title: str = ""):
        self.controller_id = controller_id
        self.port = port
        self.show_title = show_title
        self._zeroconf: Optional[AsyncZeroconf] = None
        self._info: Optional[ServiceInfo] = None

    async def start(self) -> bool:
        if not ZEROCONF_AVAILABLE:
            logger.warning("zeroconf not available; mDNS discovery disabled")
            return False
        try:
            hostname = socket.gethostname()
            ip = socket.gethostbyname(hostname)
            self._zeroconf = AsyncZeroconf()
            self._info = ServiceInfo(
                SERVICE_TYPE,
                f"CueMesh-{self.controller_id[:8]}.{SERVICE_TYPE}",
                addresses=[socket.inet_aton(ip)],
                port=self.port,
                properties={
                    b"controller_id": self.controller_id.encode(),
                    b"show_title": self.show_title.encode(),
                    b"version": b"1",
                },
            )
            await self._zeroconf.async_register_service(self._info)
            logger.info("mDNS advertisement started on %s:%d", ip, self.port)
            return True
        except Exception as e:
            logger.warning("Failed to start mDNS: %s", e)
            return False

    async def stop(self) -> None:
        if self._zeroconf and self._info:
            try:
                await self._zeroconf.async_unregister_service(self._info)
                await self._zeroconf.async_close()
            except Exception as e:
                logger.warning("Error stopping mDNS: %s", e)
        self._zeroconf = None
        self._info = None
