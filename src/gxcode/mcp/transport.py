"""MCP JSON-RPC 2.0 传输层

支持 stdio（子进程管道）和 Streamable HTTP。
"""

import asyncio
import json
import os
from abc import ABC, abstractmethod
from pathlib import Path

import httpx


class JsonRpcTransport(ABC):
    """JSON-RPC 2.0 传输抽象"""

    @abstractmethod
    async def send(self, message: dict) -> None: ...

    @abstractmethod
    async def receive(self) -> dict: ...

    @abstractmethod
    async def close(self) -> None: ...


class StdioTransport(JsonRpcTransport):
    """通过子进程 stdio 管道通信"""

    def __init__(self, command: str, args: list[str] = None, env: dict = None):
        self._command = command
        self._args = args or []
        self._env = {**os.environ, **(env or {})}
        self._proc = None
        self._reader = None
        self._writer = None

    async def connect(self) -> None:
        self._proc = await asyncio.create_subprocess_exec(
            self._command, *self._args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self._env,
        )

    async def send(self, message: dict) -> None:
        proc = self._proc  # 捕获本地引用，避免异步竞态
        if not proc or not proc.stdin:
            raise RuntimeError(f"MCP 传输未连接（server={self._command}）")
        data = json.dumps(message) + "\n"
        proc.stdin.write(data.encode())
        await proc.stdin.drain()

    async def receive(self) -> dict:
        if not self._proc or not self._proc.stdout:
            raise RuntimeError("未连接")
        line = await self._proc.stdout.readline()
        if not line:
            raise ConnectionError("子进程已关闭")
        return json.loads(line.decode())

    async def close(self) -> None:
        if self._proc:
            self._proc.terminate()
            await self._proc.wait()


class HttpTransport(JsonRpcTransport):
    """通过 Streamable HTTP 通信"""

    def __init__(self, url: str, headers: dict = None):
        self._url = url.rstrip("/")
        self._headers = headers or {}
        self._session = None

    async def connect(self) -> None:
        self._client = httpx.AsyncClient(timeout=30.0)

    async def send(self, message: dict) -> None:
        self._last_response = await self._client.post(
            self._url,
            json=message,
            headers={**self._headers, "content-type": "application/json"},
        )

    async def receive(self) -> dict:
        if self._last_response.status_code != 200:
            raise ConnectionError(f"HTTP {self._last_response.status_code}")
        return self._last_response.json()

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()