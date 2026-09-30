# GXCode Ch06 Plan — MCP 客户端

## 架构

```
mcp/
├── transport.py    ← JSON-RPC 2.0 传输层（stdio + HTTP）
├── client.py       ← MCP 客户端（三步会话）
├── adapter.py      ← MCPToolWrapper
├── manager.py      ← 连接管理
├── config.py       ← 配置加载
└── __init__.py
```

## 核心接口

```python
class McpClient:
    async def initialize() -> dict
    async def list_tools() -> list[dict]
    async def call_tool(name, args) -> dict

class MCPToolWrapper(Tool):
    def __init__(self, client, tool_def): ...
```

## 技术决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 传输 | asyncio 子进程 + httpx | 无新依赖 |
| JSON-RPC | 手动序列化 | 简单可控 |
| 适配 | 包装为 Tool 子类 | 无感注册 |