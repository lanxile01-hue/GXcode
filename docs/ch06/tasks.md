# GXCode Ch06 Tasks — MCP 客户端

## T1: 传输层 + 客户端 + 适配器
- transport.py: stdio/HTTP JSON-RPC
- client.py: initialize/list_tools/call_tool
- adapter.py: MCPToolWrapper

## T2: 管理器 + 配置
- config.py: YAML 加载 + ${VAR} 展开
- manager.py: 多 Server 连接
- __init__.py

## T3: main.py 集成
- 启动时加载 MCP 配置 → 连接 → 注册工具