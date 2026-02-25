"""CueMesh mpv controller via JSON IPC socket."""
from __future__ import annotations
import asyncio
import json
import logging
import os
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional, Any

logger = logging.getLogger("cuemesh.client.mpv")

_REQUEST_ID = 0


def _next_id() -> int:
    global _REQUEST_ID
    _REQUEST_ID += 1
    return _REQUEST_ID


class MpvController:
    """
    Controls mpv via JSON IPC socket.
    Runs mpv as a subprocess and communicates via a Unix domain socket (Linux)
    or named pipe (Windows).
    """

    def __init__(self, media_root: str = "~/cuemesh_media"):
        self.media_root = Path(media_root).expanduser()
        self._proc: Optional[subprocess.Popen] = None
        self._socket_path = str(Path(tempfile.gettempdir()) / f"cuemesh_mpv_{os.getpid()}.sock")
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._pending: dict[int, asyncio.Future] = {}
        self._running = False
        self._connected = False
        self._read_task: Optional[asyncio.Task] = None
        self.on_eof: Optional[callable] = None  # called when file ends

    async def start(self) -> bool:
        """Start mpv subprocess."""
        logger.info("Starting mpv controller...")
        
        # Clean up old socket
        if os.path.exists(self._socket_path):
            os.unlink(self._socket_path)

        cmd = [
            "mpv",
            "--no-config",
            "--idle=yes",
            "--fs",
            "--no-terminal",
            f"--input-ipc-server={self._socket_path}",
            "--keep-open=yes",
            "--loop=no",
        ]
        try:
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            logger.info("mpv process started (pid=%d)", self._proc.pid)
        except FileNotFoundError:
            logger.error("="*60)
            logger.error("MPV NOT FOUND!")
            logger.error("mpv is required for playback but is not installed.")
            logger.error("On macOS, install with: brew install mpv")
            logger.error("On Linux, install with: sudo apt install mpv")
            logger.error("="*60)
            return False

        # Wait for socket to appear
        logger.info("Waiting for mpv IPC socket at: %s", self._socket_path)
        for i in range(50):
            await asyncio.sleep(0.1)
            if os.path.exists(self._socket_path):
                logger.info("mpv IPC socket appeared after %.1fs", i * 0.1)
                break
        else:
            logger.error("mpv IPC socket did not appear after 5 seconds")
            logger.error("mpv process may have crashed. Check if mpv runs: mpv --version")
            return False

        await self._connect_socket()
        if self._connected:
            logger.info("mpv controller fully connected and ready")
        else:
            logger.error("mpv controller failed to connect to IPC socket")
        return self._connected

    async def _connect_socket(self) -> None:
        logger.debug("Attempting to connect to mpv IPC socket...")
        try:
            self._reader, self._writer = await asyncio.open_unix_connection(self._socket_path)
            self._connected = True
            self._running = True
            self._read_task = asyncio.create_task(self._read_loop())
            logger.info("Successfully connected to mpv IPC socket")
        except Exception as e:
            logger.error("Failed to connect to mpv IPC socket: %s", e)
            self._connected = False

    async def _read_loop(self) -> None:
        """Read responses from mpv."""
        while self._running and self._reader:
            try:
                line = await self._reader.readline()
                if not line:
                    break
                data = json.loads(line.decode().strip())
                # Handle events
                if "event" in data:
                    await self._handle_event(data)
                # Handle command responses
                elif "request_id" in data:
                    req_id = data["request_id"]
                    fut = self._pending.pop(req_id, None)
                    if fut and not fut.done():
                        fut.set_result(data)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug("mpv read error: %s", e)
                break

    async def _handle_event(self, data: dict) -> None:
        event = data.get("event")
        if event == "end-file" and self.on_eof:
            self.on_eof()

    async def _command(self, *args: Any) -> Optional[dict]:
        """Send a command to mpv and wait for response."""
        if not self._connected:
            logger.error("mpv not connected (cannot send command: %s)", args[0] if args else "")
            return None
        if not self._writer:
            logger.error("mpv writer is None (cannot send command: %s)", args[0] if args else "")
            return None
        
        req_id = _next_id()
        cmd = json.dumps({"command": list(args), "request_id": req_id}) + "\n"
        loop = asyncio.get_event_loop()
        fut: asyncio.Future = loop.create_future()
        self._pending[req_id] = fut
        try:
            self._writer.write(cmd.encode())
            await self._writer.drain()
            result = await asyncio.wait_for(fut, timeout=3.0)
            logger.debug("mpv command '%s' response: %s", args[0] if args else "", result)
            return result
        except asyncio.TimeoutError:
            self._pending.pop(req_id, None)
            logger.error("mpv command timed out after 3s: %s (args: %s)", args[0] if args else "", args[1:] if len(args) > 1 else "")
            return None
        except Exception as e:
            self._pending.pop(req_id, None)
            logger.error("mpv command exception: %s (command: %s)", e, args)
            return None

    async def load_file(self, rel_path: str) -> bool:
        abs_path = (self.media_root / rel_path).resolve()
        abs_path_str = str(abs_path)
        
        logger.info("Loading file: %s", abs_path_str)
        logger.debug("  Media root: %s", self.media_root)
        logger.debug("  Relative path: %s", rel_path)
        logger.debug("  mpv connected: %s, writer: %s, running: %s", self._connected, self._writer is not None, self._running)
        
        # Check mpv connection status
        if not self._connected:
            logger.error("Cannot load file: mpv is not connected")
            return False
        
        # Check if file exists
        if not abs_path.exists():
            logger.error("File does not exist: %s", abs_path_str)
            return False
        
        if not abs_path.is_file():
            logger.error("Path is not a file: %s", abs_path_str)
            return False
        
        result = await self._command("loadfile", abs_path_str, "replace")
        if result is None:
            logger.error("mpv loadfile command returned None for: %s", abs_path_str)
            logger.error("  This usually means: connection lost, timeout, or command error (check logs above)")
            return False
        
        if result.get("error") != "success":
            logger.error("mpv loadfile error response: %s for file: %s", result.get("error"), abs_path_str)
            logger.error("  Full mpv response: %s", result)
            return False
            
        logger.info("Successfully loaded file: %s", abs_path_str)
        return True

    async def play(self) -> None:
        await self._command("set_property", "pause", False)

    async def pause(self) -> None:
        await self._command("set_property", "pause", True)

    async def stop(self) -> None:
        await self._command("stop")

    async def seek(self, position_ms: int) -> None:
        await self._command("seek", position_ms / 1000.0, "absolute")

    async def get_position_ms(self) -> Optional[int]:
        result = await self._command("get_property", "time-pos")
        if result and result.get("error") == "success":
            val = result.get("data")
            if val is not None:
                return int(float(val) * 1000)
        return None

    async def set_speed(self, rate: float) -> None:
        await self._command("set_property", "speed", rate)

    async def set_volume(self, volume: int) -> None:
        # mpv volume 0-100
        await self._command("set_property", "volume", max(0, min(100, volume)))

    async def set_loop(self, loop: bool) -> None:
        await self._command("set_property", "loop-file", "inf" if loop else "no")

    async def set_fullscreen(self, on: bool = True) -> None:
        await self._command("set_property", "fullscreen", on)

    async def blackout(self) -> None:
        """Show black screen."""
        await self.stop()
        # Load a black frame via lavfi
        await self._command("loadfile", "lavfi://color=black:s=1920x1080:d=86400", "replace")

    async def show_testscreen(self, on: bool) -> None:
        """Show/hide test screen (SMPTE color bars via lavfi)."""
        if on:
            await self._command("loadfile", "lavfi://smptebars=s=1920x1080:d=86400", "replace")
        else:
            await self.stop()

    async def stop_subprocess(self) -> None:
        """Terminate mpv."""
        self._running = False
        self._connected = False
        if self._read_task:
            self._read_task.cancel()
        if self._writer:
            try:
                self._writer.close()
            except Exception:
                pass
        if self._proc:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=3)
            except Exception:
                self._proc.kill()
        if os.path.exists(self._socket_path):
            os.unlink(self._socket_path)
        logger.info("mpv stopped")

    @property
    def is_connected(self) -> bool:
        return self._connected
