from __future__ import annotations

import asyncio
import logging
import os
import shutil
import time
from asyncio.subprocess import Process

import httpx

from opencode_mcp.errors import (
    OpencodeBinaryNotFoundError,
    OpencodeStartupError,
)

logger = logging.getLogger(__name__)


class OpencodeProcess:
    def __init__(
        self,
        model: str = "ollama/qwen3.5:cloud",
        port: int = 0,
        startup_timeout: float = 10.0,
        password: str | None = None,
    ) -> None:
        self._model = model
        self._requested_port = port
        self._startup_timeout = startup_timeout
        self._password = password or os.getenv("OPENCODE_SERVER_PASSWORD")
        self._process: Process | None = None
        self._port: int | None = None

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.returncode is None

    @property
    def base_url(self) -> str:
        if self._port is None:
            raise RuntimeError("opencode process not started")
        return f"http://127.0.0.1:{self._port}"

    @property
    def auth(self) -> tuple[str, str] | None:
        if self._password:
            return ("opencode", self._password)
        return None

    async def start(self) -> None:
        self._assert_binary_exists()
        port = self._requested_port if self._requested_port != 0 else self._find_free_port()
        await self._spawn(port)
        await self._wait_for_healthy()

    async def stop(self) -> None:
        if self._process is None:
            return
        try:
            self._process.terminate()
            await asyncio.wait_for(self._process.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            self._process.kill()
        finally:
            self._process = None
            self._port = None

    async def restart(self) -> None:
        await self.stop()
        await self.start()

    def _assert_binary_exists(self) -> None:
        if shutil.which("opencode") is None:
            raise OpencodeBinaryNotFoundError()

    def _find_free_port(self) -> int:
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]

    async def _spawn(self, port: int) -> None:
        cmd = [
            "opencode", "serve",
            "--port", str(port),
            "--hostname", "127.0.0.1",
        ]
        env = os.environ.copy()
        if self._password:
            env["OPENCODE_SERVER_PASSWORD"] = self._password

        logger.info("Starting opencode server on port %d with model %s", port, self._model)
        self._process = await asyncio.create_subprocess_exec(
            *cmd,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self._port = port

    async def _wait_for_healthy(self) -> None:
        deadline = time.monotonic() + self._startup_timeout
        url = f"{self.base_url}/global/health"
        auth = self.auth

        async with httpx.AsyncClient() as client:
            while time.monotonic() < deadline:
                if self._process and self._process.returncode is not None:
                    stderr = b""
                    if self._process.stderr:
                        stderr = await self._process.stderr.read()
                    raise OpencodeStartupError(
                        message="opencode process exited unexpectedly during startup",
                        detail={"stderr": stderr.decode(errors="replace")},
                        recoverable=False,
                        suggestion="Check that opencode is correctly installed and the model is available",
                    )
                try:
                    response = await client.get(url, auth=auth, timeout=1.0)
                    if response.status_code == 200:
                        logger.info("opencode server is healthy at %s", self.base_url)
                        return
                except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout):
                    pass
                await asyncio.sleep(0.5)

        stderr_output = ""
        if self._process and self._process.stderr:
            try:
                stderr_output = (await asyncio.wait_for(self._process.stderr.read(), timeout=1.0)).decode(errors="replace")
            except asyncio.TimeoutError:
                pass
        await self.stop()
        raise OpencodeStartupError(
            message=f"opencode server did not become healthy within {self._startup_timeout}s",
            detail={"stderr": stderr_output},
            recoverable=False,
            suggestion="Try increasing OPENCODE_STARTUP_TIMEOUT or check opencode logs",
        )
