"""GXCode Skill 加载器

YAML frontmatter + Markdown 解析，三级目录扫描，同名按优先级覆盖。
解析失败的单文件跳过不阻断整体。
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

# frontmatter 正则
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


@dataclass
class Skill:
    """一个 Skill 定义"""
    name: str
    desc: str = ""
    tools: list[str] = field(default_factory=list)
    mode: str = "shared"          # "shared" | "isolated"
    history: int = 0              # isolated 模式带回的历史轮数
    model: str = ""               # 可选指定模型
    params: list[str] = field(default_factory=list)
    body: str = ""                # SOP 正文（Markdown，支持 {{param}} 占位符）

    @property
    def summary(self) -> str:
        """一行摘要：/name — desc"""
        return f"/{self.name} — {self.desc}"


class SkillLoader:
    """三级 Skill 加载器

    扫描顺序（优先级从低到高）：
    1. 内置: src/gxcode/skills/builtin/
    2. 用户: ~/.gxcode/skills/
    3. 项目: .gxcode/skills/

    同名 Skill 后加载的覆盖先加载的。
    """

    def __init__(self, project_root: Path):
        self._project_root = project_root

    def load_all(self) -> dict[str, Skill]:
        """加载所有 Skill，返回 name -> Skill 映射"""
        result: dict[str, Skill] = {}

        # 1. 内置（最低优先级）
        builtin_dir = Path(__file__).parent / "builtin"
        if builtin_dir.is_dir():
            _scan_dir(builtin_dir, result)

        # 2. 用户级
        user_dir = Path.home() / ".gxcode" / "skills"
        if user_dir.is_dir():
            _scan_dir(user_dir, result)

        # 3. 项目级（最高优先级）
        project_dir = self._project_root / ".gxcode" / "skills"
        if project_dir.is_dir():
            _scan_dir(project_dir, result)

        return result


def _scan_dir(directory: Path, result: dict[str, Skill]) -> None:
    """扫描目录中的 .md 文件，解析 Skill 并覆盖同名"""
    for f in sorted(directory.glob("*.md")):
        skill = _parse_skill_file(f)
        if skill:
            result[skill.name] = skill


def _parse_skill_file(file_path: Path) -> Skill | None:
    """解析单个 Skill 文件"""
    try:
        text = file_path.read_text(encoding="utf-8")
    except OSError:
        return None

    m = _FRONTMATTER_RE.match(text)
    if not m:
        return None

    fm_text = m.group(1)
    body = text[m.end():].strip()

    # 手动 YAML 行解析
    fields: dict[str, str] = {}
    for line in fm_text.split("\n"):
        line = line.strip()
        if ":" in line:
            key, _, val = line.partition(":")
            fields[key.strip()] = val.strip()

    if "name" not in fields:
        return None

    # 解析 tools 列表
    tools: list[str] = []
    tools_raw = fields.get("tools", "[]")
    if tools_raw.startswith("[") and tools_raw.endswith("]"):
        inner = tools_raw[1:-1]
        tools = [t.strip().strip("\"'") for t in inner.split(",") if t.strip()]

    # 解析 params 列表
    params: list[str] = []
    params_raw = fields.get("params", "[]")
    if params_raw.startswith("[") and params_raw.endswith("]"):
        inner = params_raw[1:-1]
        params = [p.strip().strip("\"'") for p in inner.split(",") if p.strip()]

    # 兼容 GitHub skills 的 description 字段
    desc = fields.get("desc", "") or fields.get("description", "")

    return Skill(
        name=fields["name"],
        desc=desc,
        tools=tools,
        mode=fields.get("mode", "shared"),
        history=int(fields.get("history", 0)),
        model=fields.get("model", ""),
        params=params,
        body=body,
    )