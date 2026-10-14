"""GXCode CLI 入口

Ch06: 启动时自动发现 MCP Server 并注册工具。
Ch07: 初始化双层上下文压缩组件。
Ch08: 加载项目记忆（指令+笔记），注入系统提示。
"""

import argparse
import asyncio
import sys
from pathlib import Path

from gxcode.agent import build_act_prompt
from gxcode.config import load_config, get_active
from gxcode.context import ContextManager, Summarizer, TokenCounter
from gxcode.mcp import MCPManager, load_mcp_config
from gxcode.memory import NoteManager, NoteWriter, SessionStore, build_memory_context
from gxcode.permission import PermissionChecker, PermissionMode
from gxcode.provider import create_provider
from gxcode.session import ChatSession
from gxcode.skills import InstallSkillTool, LoadSkillTool, SkillLoader, SkillRegistry, ToolWhitelist
from gxcode.tools import ToolRegistry
from gxcode.tui.app import GXCodeApp


async def _connect_mcp() -> ToolRegistry:
    """连接 MCP Server 并返回合并后的工具注册中心"""
    mcp_config = load_mcp_config()
    manager = MCPManager()
    return await manager.connect_all(mcp_config)


async def _async_main(config_path: str) -> None:
    """异步主入口 — MCP 连接和 Textual app 共享同一事件循环"""
    project_root = Path.cwd()

    # 加载 LLM 配置
    try:
        app_config = load_config(config_path)
    except FileNotFoundError as e:
        print(f"错误: {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"配置错误: {e}")
        sys.exit(1)

    active = get_active(app_config)

    # 加载 MCP 配置并连接 Server（与 Textual 共享事件循环，避免 transport 失效）
    registry = await _connect_mcp()
    tools_schema = registry.to_api_schema()

    # Skill 加载
    skill_loader = SkillLoader(project_root)
    skill_map = skill_loader.load_all()
    # 启动时验证白名单工具
    whitelist = ToolWhitelist([t["function"]["name"] for t in tools_schema])
    for skill in skill_map.values():
        if skill.tools:
            whitelist.validate(skill.tools, skill.name)
    skill_registry = SkillRegistry(skill_map)
    # 注册 load_skill 和 install_skill 工具
    registry.register(LoadSkillTool(skill_registry, whitelist))
    registry.register(InstallSkillTool(skill_registry))
    # 重新生成 schema（含 load_skill + install_skill）
    tools_schema = registry.to_api_schema()

    # Provider
    try:
        provider = create_provider(active, tools=tools_schema)
        # 摘要用 Provider（不带 tools，防止摘要 LLM 调工具）
        summary_provider = create_provider(active, tools=None)
        # 笔记用 Provider（不带 tools，防止笔记 LLM 调工具）
        note_provider = create_provider(active, tools=None)
    except ValueError as e:
        print(f"错误: {e}")
        sys.exit(1)

    # 加载记忆上下文（指令 + 笔记索引）
    memory_context = build_memory_context(project_root)

    # System prompt（拼接记忆上下文）
    base_prompt = build_act_prompt(registry.list_all())
    system_prompt = f"{base_prompt}\n\n{memory_context}" if memory_context else base_prompt

    # Skill 摘要注入
    skill_summary = skill_registry.get_summary()
    if skill_summary:
        system_prompt = f"{system_prompt}\n\n{skill_summary}"

    session = ChatSession(
        provider=provider,
        model=active.model,
        thinking=active.thinking,
        system_prompt=system_prompt,
    )

    # 接入会话 JSONL 存储
    store = SessionStore(project_root / ".gxcode" / "sessions")
    session.set_store(store)

    # 上下文压缩组件
    counter = TokenCounter()
    summarizer = Summarizer(
        provider=summary_provider,
        model=active.model,
        max_failures=app_config.context.max_summary_failures,
    )
    ctx_mgr = ContextManager(
        session=session,
        counter=counter,
        summarizer=summarizer,
        config=app_config.context,
    )

    permission = PermissionChecker(mode=PermissionMode.DEFAULT, project_root=".")
    note_writer = NoteWriter(
        provider=note_provider,
        model=active.model,
        project_mgr=NoteManager(project_root / ".gxcode" / "memory"),
        user_mgr=NoteManager(Path.home() / ".gxcode" / "memory"),
    )
    app = GXCodeApp(session, registry, permission_checker=permission, context_manager=ctx_mgr, note_writer=note_writer, skill_registry=skill_registry)
    await app.run_async()


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="gxcode",
        description="GXCode — 命令行 AI 对话助手",
    )
    parser.add_argument(
        "--config",
        default="./gxcode.yaml",
        help="YAML 配置文件路径（默认: ./gxcode.yaml）",
    )
    args = parser.parse_args()
    asyncio.run(_async_main(args.config))


if __name__ == "__main__":
    main()