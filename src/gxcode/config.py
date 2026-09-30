"""GXCode YAML 配置加载"""

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class ProviderConfig:
    """单个 LLM 供应商配置"""
    name: str
    protocol: str          # "anthropic" | "openai"
    model: str
    base_url: str
    api_key: str
    thinking: bool = False


@dataclass
class AppConfig:
    """应用顶层配置"""
    providers: list[ProviderConfig] = field(default_factory=list)
    active: str = ""       # 当前激活的 provider name
    context: "ContextConfig" = field(default_factory=lambda: ContextConfig())
    memory: "MemoryConfig" = field(default_factory=lambda: MemoryConfig())


@dataclass
class ContextConfig:
    """上下文管理配置（可选节 context:）"""
    # 窗口与余量
    window_size: int = 200_000
    auto_margin: int = 13_000
    manual_margin: int = 3_000
    # 轻量预防
    spill_dir: str = ".gxcode/spills"
    # 阈值单位是字符。8000 字符 ≈ 2000 token，对本项目 12~18KB 的源码文件来说太低，
    # 会导致「读任何正常文件都被溢写」，进而诱发模型整文件重读溢写文件的套娃。
    # 提到 32000/64000（≈8K/16K token）后，常规源码文件可正常读取。
    single_threshold: int = 32_000
    batch_threshold: int = 64_000
    # 重量兜底
    keep_tokens: int = 10_000
    keep_min: int = 5
    # 熔断
    max_summary_failures: int = 3


@dataclass
class MemoryConfig:
    """记忆管理配置（可选节 memory:）"""
    max_include_depth: int = 3       # @include 最大嵌套深度
    cleanup_days: int = 30           # 会话清理天数
    note_update_enabled: bool = True # 是否启用自动笔记


def load_config(path: str) -> AppConfig:
    """从 YAML 文件加载配置

    验证必填字段，返回 AppConfig。

    Raises:
        FileNotFoundError: 配置文件不存在
        ValueError: 配置格式错误或缺少必填字段
    """
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {path}")

    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if raw is None:
        raise ValueError("配置文件为空")

    if "providers" not in raw:
        raise ValueError("配置文件缺少 'providers' 字段")

    if "active" not in raw:
        raise ValueError("配置文件缺少 'active' 字段")

    providers = []
    for entry in raw["providers"]:
        _validate_provider_entry(entry)
        providers.append(ProviderConfig(
            name=entry["name"],
            protocol=entry["protocol"],
            model=entry["model"],
            base_url=entry["base_url"],
            api_key=entry["api_key"],
            thinking=entry.get("thinking", False),
        ))

    active = raw["active"]
    # 验证 active 指向的 provider 存在
    if not any(p.name == active for p in providers):
        raise ValueError(f"active='{active}' 不匹配任何 provider name，可用: {[p.name for p in providers]}")

    # 解析可选的 context 节
    context = ContextConfig()
    if "context" in raw:
        ctx = raw["context"]
        if isinstance(ctx, dict):
            context = ContextConfig(
                window_size=ctx.get("window_size", context.window_size),
                auto_margin=ctx.get("auto_margin", context.auto_margin),
                manual_margin=ctx.get("manual_margin", context.manual_margin),
                spill_dir=ctx.get("spill_dir", context.spill_dir),
                single_threshold=ctx.get("single_threshold", context.single_threshold),
                batch_threshold=ctx.get("batch_threshold", context.batch_threshold),
                keep_tokens=ctx.get("keep_tokens", context.keep_tokens),
                keep_min=ctx.get("keep_min", context.keep_min),
                max_summary_failures=ctx.get("max_summary_failures", context.max_summary_failures),
            )

    # 解析可选的 memory 节
    memory = MemoryConfig()
    if "memory" in raw:
        mem = raw["memory"]
        if isinstance(mem, dict):
            memory = MemoryConfig(
                max_include_depth=mem.get("max_include_depth", memory.max_include_depth),
                cleanup_days=mem.get("cleanup_days", memory.cleanup_days),
                note_update_enabled=mem.get("note_update_enabled", memory.note_update_enabled),
            )

    return AppConfig(providers=providers, active=active, context=context, memory=memory)


def get_active(config: AppConfig) -> ProviderConfig:
    """获取当前激活的供应商配置"""
    for p in config.providers:
        if p.name == config.active:
            return p
    raise ValueError(f"active='{config.active}' 不匹配任何已知 provider")


def _validate_provider_entry(entry: dict) -> None:
    """验证单个 provider 条目"""
    required = ["name", "protocol", "model", "base_url", "api_key"]
    for field_name in required:
        if field_name not in entry:
            raise ValueError(f"provider 条目缺少必填字段 '{field_name}'")

    if entry["protocol"] not in ("anthropic", "openai"):
        raise ValueError(f"不支持的 protocol: '{entry['protocol']}'，仅支持 anthropic/openai")