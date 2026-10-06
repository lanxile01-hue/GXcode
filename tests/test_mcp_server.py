"""最小 MCP Server — 提供 echo 和 get_time 两个工具"""
import json
import sys
from datetime import datetime


def handle_request(req):
    method = req.get("method", "")
    req_id = req.get("id")

    if method == "initialize":
        return {"jsonrpc": "2.0", "id": req_id, "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "test-server", "version": "1.0.0"},
        }}

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": [
            {
                "name": "echo",
                "description": "回显输入的消息",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "message": {"type": "string", "description": "要回显的消息"},
                    },
                    "required": ["message"],
                },
            },
            {
                "name": "get_time",
                "description": "获取当前时间",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
        ]}}

    if method == "tools/call":
        params = req.get("params", {})
        name = params.get("name", "")
        args = params.get("arguments", {})

        if name == "echo":
            text = args.get("message", "")
            result = {"content": [{"type": "text", "text": f"Echo: {text}"}]}
        elif name == "get_time":
            now = datetime.now().isoformat()
            result = {"content": [{"type": "text", "text": f"当前时间: {now}"}]}
        else:
            result = {"content": [{"type": "text", "text": f"未知工具: {name}"}]}

        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    # notifications (no id) — ignore
    if "id" not in req:
        return None

    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"未知方法: {method}"}}


def main():
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            req = json.loads(line)
            resp = handle_request(req)
            if resp:
                sys.stdout.write(json.dumps(resp) + "\n")
                sys.stdout.flush()
        except Exception:
            break


if __name__ == "__main__":
    main()