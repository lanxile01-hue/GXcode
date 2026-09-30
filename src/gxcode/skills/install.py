"""GXCode Skill 远程安装工具

从 skills.sh 拉取 Skill 文件并安装到本地用户目录。
"""

import asyncio
import re
import urllib.request
from pathlib import Path

from gxcode.skills.loader import _parse_skill_file
from gxcode.skills.registry import SkillRegistry
from gxcode.tools.base import Tool, ToolResult

# URL pattern: skills.sh/{owner}/{repo}/{skill_name}
_SKILLS_SH_RE = re.compile(r"skills\.sh/([^/]+)/([^/]+)/([^/\s?#]+)")


class InstallSkillTool(Tool):
    """从 skills.sh 安装 Skill 到本地"""

    name = "install_skill"
    description = (
        "从 skills.sh 安装一个 Skill 到本地用户目录。"
        "参数: url (skills.sh 链接，格式 https://www.skills.sh/{owner}/{repo}/{skill_name})"
    )
    parameters = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "skills.sh 上的 Skill 链接",
            },
        },
        "required": ["url"],
    }
    is_safe = False  # 写文件

    def __init__(self, skill_registry: SkillRegistry):
        super().__init__()
        self._registry = skill_registry

    async def execute(self, url: str) -> ToolResult:
        # 1. 解析 URL
        m = _SKILLS_SH_RE.search(url)
        if not m:
            return ToolResult.fail(
                f"无法解析 skills.sh 链接: {url}\n"
                "格式: https://www.skills.sh/{owner}/{repo}/{skill_name}"
            )

        owner, repo, skill_name = m.group(1), m.group(2), m.group(3)

        # 2. 构造 GitHub raw URL
        raw_url = (
            f"https://raw.githubusercontent.com/{owner}/{repo}"
            f"/main/skills/{skill_name}/SKILL.md"
        )

        # 3. 下载
        try:
            content = await self._fetch(raw_url)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return ToolResult.fail(
                    f"Skill '{skill_name}' 在 {owner}/{repo} 中不存在。"
                )
            return ToolResult.fail(f"下载失败 (HTTP {e.code}): {raw_url}")
        except Exception as e:
            return ToolResult.fail(f"下载失败: {e}\n{raw_url}")

        # 4. 保存到 ~/.gxcode/skills/
        target_dir = Path.home() / ".gxcode" / "skills"
        target_dir.mkdir(parents=True, exist_ok=True)
        target_file = target_dir / f"{skill_name}.md"

        try:
            target_file.write_text(content, encoding="utf-8")
        except OSError as e:
            return ToolResult.fail(f"写入文件失败: {e}")

        # 5. 更新内存中的 registry（立即可用）
        skill = _parse_skill_file(target_file)
        if skill:
            self._registry._skills[skill.name] = skill

        return ToolResult.ok(
            f"Skill '{skill_name}' 已安装到 {target_file}\n"
            f"路径: {raw_url}\n"
            f"现在可以用 load_skill 激活它了。"
        )

    async def _fetch(self, url: str) -> str:
        """异步 HTTP GET，返回解码后的文本"""
        loop = asyncio.get_running_loop()

        def _sync_fetch() -> str:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "GXCode/1.0"},
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.read().decode("utf-8")

        return await loop.run_in_executor(None, _sync_fetch)