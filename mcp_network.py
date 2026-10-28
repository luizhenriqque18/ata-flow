"""Ciclo de vida do servidor HTTP embutido, sem interferir nos sinais da TUI."""

from __future__ import annotations

import asyncio
import socket
from contextlib import contextmanager, suppress

import uvicorn

from mcp_settings import MCPSettingsStore


class EmbeddedServer(uvicorn.Server):
    @contextmanager
    def capture_signals(self):
        # Ctrl+C e o encerramento pertencem ao Textual.
        yield


class MCPHTTPService:
    def __init__(self, store: MCPSettingsStore | None = None) -> None:
        self.store = store or MCPSettingsStore()
        self.server: EmbeddedServer | None = None
        self.task: asyncio.Task | None = None
        self.socket: socket.socket | None = None
        self._configuration = None
        self._lock = asyncio.Lock()

    @property
    def running(self) -> bool:
        return bool(self.server and self.server.started and self.task and not self.task.done())

    async def apply(self) -> None:
        async with self._lock:
            await self._apply()

    async def _apply(self) -> None:
        try:
            settings = self.store.load()
        except (ValueError, OSError):
            await self.stop()
            raise
        configuration = (settings.http_host, settings.http_port, settings.http_public_host)
        if not settings.enabled or not settings.network_enabled:
            await self.stop()
            return
        if self.running and configuration == self._configuration:
            return
        await self.stop()
        from ataflow_mcp import create_http_app

        app = create_http_app(self.store)
        family = socket.AF_INET6 if ":" in settings.http_host else socket.AF_INET
        listener = socket.socket(family, socket.SOCK_STREAM)
        self.socket = listener
        try:
            # Bind explícito faz conflitos de porta virarem OSError, sem SystemExit do uvicorn.
            listener.bind((settings.http_host, settings.http_port))
            listener.listen(128)
            listener.setblocking(False)
            self.server = EmbeddedServer(
                uvicorn.Config(
                    app,
                    host=settings.http_host,
                    port=settings.http_port,
                    access_log=False,
                    log_level="warning",
                    timeout_graceful_shutdown=2,
                )
            )
            self.task = asyncio.create_task(self.server.serve(sockets=[listener]))
            for _ in range(100):
                if self.running:
                    self._configuration = configuration
                    return
                if self.task.done():
                    await self.task
                    raise OSError("Servidor HTTP encerrou antes de iniciar.")
                await asyncio.sleep(0.05)
            raise OSError("Servidor HTTP não iniciou no tempo esperado.")
        except BaseException:
            await self.stop()
            raise

    async def stop(self) -> None:
        if self.server:
            self.server.should_exit = True
        if self.task:
            try:
                await asyncio.wait_for(asyncio.shield(self.task), timeout=4)
            except TimeoutError:
                self.task.cancel()
                with suppress(asyncio.CancelledError):
                    await self.task
            finally:
                self.task = None
                self.server = None
                if self.socket:
                    self.socket.close()
                    self.socket = None
        elif self.socket:
            self.socket.close()
            self.socket = None
        self._configuration = None
