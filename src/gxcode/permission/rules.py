"""GXCode 权限规则引擎

从三层 YAML 文件加载规则，用 fnmatch 做工具名和参数的 glob 匹配。
"""

import fnmatch
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class Rule:
    """单条权限规则"""
    tool: str       # 工具名模式（支持 glob）
    param: str      # 参数模式（支持 glob）
    allow: bool     # True=allow, False=deny
    param_key: str | None = None  # 可选：指定匹配哪个参数名，None=匹配全部参数值


class RuleEngine:
    """权限规则引擎 — 加载三层 YAML，逐层匹配"""

    def __init__(self, project_root: str):
        self._rules: list[list[Rule]] = []  # [session_rules, project_rules, global_rules]
        self._project_root = Path(project_root)
        self._load_rules()

    def _load_rules(self) -> None:
        """加载三层规则（优先级递增）"""
        layers = [
            Path.home() / ".gxcode" / "rules.yaml",          # 全局（低）
            self._project_root / ".gxcode" / "rules.yaml",   # 项目（中）
            # 会话规则（高）由 add_session_rule 动态追加
        ]
        for path in layers:
            rules = self._load_yaml(path)
            self._rules.append(rules)
        self._rules.append([])  # 会话规则占位

    def _load_yaml(self, path: Path) -> list[Rule]:
        """从 YAML 文件加载规则"""
        if not path.exists():
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = yaml.safe_load(f)
            if not raw or "rules" not in raw:
                return []
            rules = []
            for entry in raw["rules"]:
                rule = self._parse_rule(entry)
                if rule:
                    rules.append(rule)
            return rules
        except Exception:
            return []

    def _parse_rule(self, entry: str) -> Rule | None:
        """解析单条规则：'write_file(path: *.env): deny' → Rule

        支持两种写法：
          - 无参数名：'run_command(git *): allow' → 对全部参数值做 glob
          - 带参数名：'write_file(path: *.env): deny' → 只对 path 参数做 glob
        """
        entry = entry.strip()
        if ":" not in entry:
            return None

        pattern, action = entry.rsplit(":", 1)
        pattern = pattern.strip()
        action = action.strip().lower()

        if action not in ("allow", "deny"):
            return None

        # 解析 工具名(参数模式)
        if "(" not in pattern or not pattern.endswith(")"):
            return None

        tool, param = pattern[:-1].split("(", 1)
        tool = tool.strip()
        param = param.strip()

        # 带参数名：write_file(path: *.env) → 参数名="path"，模式="*.env"
        param_key: str | None = None
        if ":" in param:
            key, value = param.split(":", 1)
            param_key = key.strip()
            param = value.strip()

        return Rule(tool=tool, param=param, allow=(action == "allow"), param_key=param_key)

    def add_session_rule(self, rule: Rule) -> None:
        """动态追加会话级临时规则"""
        self._rules[-1].append(rule)

    def match(self, tool_name: str, **params) -> bool | None:
        """匹配规则，优先级从高到低

        Returns:
            True=allow, False=deny, None=未命中
        """
        # 从高优先级往低查（倒序）
        for layer in reversed(self._rules):
            for rule in layer:
                if not fnmatch.fnmatch(tool_name, rule.tool):
                    continue
                if self._rule_param_matches(rule, params):
                    return rule.allow

        return None  # 未命中

    def _rule_param_matches(self, rule: Rule, params: dict) -> bool:
        """判断某条规则的参数模式是否命中实际参数

        - 规则带 param_key：只对该参数值做 glob
        - 规则不带 param_key：对全部参数值做 glob（任一命中即算）
        """
        if rule.param_key is not None:
            value = params.get(rule.param_key)
            if value is None:
                return False
            return fnmatch.fnmatch(str(value), rule.param)

        # 无参数名：任一参数值命中即算
        for value in params.values():
            if fnmatch.fnmatch(str(value), rule.param):
                return True
        return False
