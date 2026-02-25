"""CueMesh client mDNS browser to discover controller."""
from __future__ import annotations
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional, Callable

try:
    from zeroconf import ServiceBrowser, ServiceListener, Zeroconf
    from zeroconf.asyncio import AsyncZeroconf, AsyncServiceBrowser
    ZEROCONF_AVAILABLE = True
except ImportError:
    ZEROCONF_AVAILABLE = False

logger = logging.getLogger("cuemesh.client.discovery")

SERVICE_TYPE = "_cuemesh._tcp.local."


@dataclass
class DiscoveredController:
    name: str
    host: str
    port: int
    controller_id: str = ""
    show_title: str = ""


class DiscoveryBrowser:
    """Browses mDNS for CueMesh controller services."""

    def __init__(self, on_found: Optional[Callable[[DiscoveredController], None]] = None):
        self.on_found = on_found
        self._discovered: dict[str, DiscoveredController] = {}
        self._zeroconf: Optional[AsyncZeroconf] = None
        self._browser = None

    async def start(self) -> bool:
        if not ZEROCONF_AVAILABLE:
            logger.warning("zeroconf not available; mDNS discovery disabled")
            return False
        try:
            self._zeroconf = AsyncZeroconf()
            from zeroconf import ServiceBrowser

            def on_service_state_change(zeroconf_instance, service_type, name, state_change):
                from zeroconf import ServiceStateChange
                if state_change == ServiceStateChange.Added:
                    asyncio.get_event_loop().call_soon_threadsafe(
                        lambda: asyncio.ensure_future(
                            self._on_service_added(zeroconf_instance, service_type, name)
                        )
                    )

            self._browser = ServiceBrowser(
                self._zeroconf.zeroconf, SERVICE_TYPE, handlers=[on_service_state_change]
            )
            logger.info("mDNS browser started")
            return True
        except Exception as e:
            logger.warning("Failed to start mDNS browser: %s", e)
            return False

    async def _on_service_added(self, zeroconf, service_type: str, name: str) -> None:
        try:
            info = zeroconf.get_service_info(service_type, name)
            if info is None:
                return
            import socket
            host = socket.inet_ntoa(info.addresses[0]) if info.addresses else "unknown"
            props = info.properties or {}
            controller_id = props.get(b"controller_id", b"").decode()
            show_title = props.get(b"show_title", b"").decode()
            dc = DiscoveredController(
                name=name,
                host=host,
                port=info.port,
                controller_id=controller_id,
                show_title=show_title,
            )
            self._discovered[name] = dc
            logger.info("Discovered controller: %s @ %s:%d", controller_id, host, info.port)
            if self.on_found:
                self.on_found(dc)
        except Exception as e:
            logger.warning("Error processing discovered service: %s", e)

    async def stop(self) -> None:
        if self._zeroconf:
            try:
                await self._zeroconf.async_close()
            except Exception:
                pass
        self._zeroconf = None

    @property
    def discovered(self) -> list[DiscoveredController]:
        return list(self._discovered.values())
