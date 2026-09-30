"""MCP 配置加载 — YAML + ${VAR} 展开 + 两层合并"""

import os
import re
from pathlib import Path

import yaml

_VAR_RE = re.compile(r"\$\{(\w+)\}")


def _expand_env(value: str) -> str:
    """展开 ${VAR} 环境变量"""
    def replacer(m):
        return os.environ.get(m.group(1), "")
    return _VAR_RE.sub(replacer, value)


def load_mcp_config(project_root: str = ".") -> dict:
    """加载 MCP Server 配置（用户级 + 项目级合并）

    Returns:
        {"server_name": {"type": "stdio", "command": "...", ...}, ...}
    """
    config = {}

    # 用户全局
    user_path = Path.home() / ".gxcode" / "mcp_servers.yaml"
    if user_path.exists():
        try:
            with open(user_path, "r", encoding="utf-8") as f:
                raw = yaml.safe_load(f)
            if raw and "servers" in raw:
                config.update(raw["servers"])
        except Exception:
            pass

    # 项目级覆盖
    project_path = Path(project_root) / ".gxcode" / "mcp_servers.yaml"
    if project_path.exists():
        try:
            with open(project_path, "r", encoding="utf-8") as f:
                raw = yaml.safe_load(f)
            if raw and "servers" in raw:
                config.update(raw["servers"])
        except Exception:
            pass

    # 环境变量展开
    expanded = {}
    for name, server in config.items():
        expanded[name] = {}
        for key, value in server.items():
            if isinstance(value, str):
                expanded[name][key] = _expand_env(value)
            elif isinstance(value, dict):
                expanded[name][key] = {
                    k: _expand_env(v) if isinstance(v, str) else v
                    for k, v in value.items()
                }
            elif isinstance(value, list):
                expanded[name][key] = [
                    _expand_env(v) if isinstance(v, str) else v
                    for v in value
                ]
            else:
                expanded[name][key] = value
    return expanded