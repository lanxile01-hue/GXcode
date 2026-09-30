"""GXCode 轻量预防 — 工具结果溢写

单条工具结果超阈值 → 存盘，对话留预览 + 路径
多工具结果合计超阈值 → 挑最大的依次存盘
用户消息不动，只处理工具结果消息（原生 role="tool" 和旧版
"[tool_result from xxx]" 用户消息两种格式都支持）。

防递归：模型按预览提示用 read_file 整文件重读溢写文件时，读回来的内容
还是同一份超阈值负载。若不拦截，会「溢写 → 重读 → 再溢写」无限套娃。
因此同一份内容只溢写一次（按内容哈希记账），重复读取改为硬提示。
"""

import hashlib
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from gxcode.types_ import Message

# 匹配旧版 tool_result 消息前缀: [tool_result from xxx]
_TOOL_RESULT_RE = re.compile(r"^\[tool_result from (.+?)\]\n", re.DOTALL)

# 预览保留的字符数
PREVIEW_CHARS = 500

# 提醒模型按片段读取，而不是整文件重读
_SLICE_HINT = (
    "需要定位关键内容请用 grep_search；需要片段请用 run_command 分片读取"
    "（如 `sed -n '1,80p' 路径`，Windows 用 `findstr /n 模式 路径` 或 `more +行号 路径`）"
)


@dataclass
class SpillResult:
    """溢写结果"""
    messages: list[Message]
    spilled_paths: list[str] = field(default_factory=list)


def spill_files(
    messages: list[Message],
    spill_dir: Path,
    single_threshold: int = 8000,
    batch_threshold: int = 16000,
    spilled_hashes: set[str] | None = None,
) -> SpillResult:
    """溢写超阈值工具结果到磁盘

    策略：
    1. 单条 tool_result 字符数超过 single_threshold → 存盘
    2. 所有 tool_result 合计超过 batch_threshold → 按大小降序存盘

    Args:
        messages: 当前消息列表
        spill_dir: 溢写文件存放目录
        single_threshold: 单条结果字符数阈值
        batch_threshold: 所有工具结果合计字符数阈值
        spilled_hashes: 已溢写内容哈希集合（跨调用复用可拦截重复溢写；
            传入同一集合即可获得"同一内容只溢写一次"的语义）

    Returns:
        SpillResult: 修改后的消息列表和溢写文件路径
    """
    spill_dir.mkdir(parents=True, exist_ok=True)
    result = [m for m in messages]  # 浅拷贝
    spilled_paths: list[str] = []
    seen = spilled_hashes if spilled_hashes is not None else set()
    tool_indices = _find_tool_results(result)

    if not tool_indices:
        return SpillResult(messages=result, spilled_paths=spilled_paths)

    # ── 阶段 1：单条超阈值 ──
    for idx in tool_indices:
        tool_name, payload = _parse_tool_result(result[idx])
        if tool_name is None:
            continue
        if len(payload) > single_threshold:
            digest = _digest(payload)
            if digest in seen:
                # 这段内容已经溢写过 → 模型正在重读溢写文件本身，不能再溢写
                result[idx] = _make_reread_msg(result[idx], tool_name, payload)
                continue
            file_path = _save_to_disk(spill_dir, payload)
            seen.add(digest)
            spilled_paths.append(file_path)
            result[idx] = _make_preview_msg(result[idx], tool_name, file_path, payload)

    # ── 阶段 2：合计超阈值 ──
    # 重新扫描（阶段 1 可能改变了消息内容）
    tool_indices = _find_tool_results(result)
    if not tool_indices:
        return SpillResult(messages=result, spilled_paths=spilled_paths)

    total_chars = sum(len(result[i].content) for i in tool_indices)
    if total_chars <= batch_threshold:
        return SpillResult(messages=result, spilled_paths=spilled_paths)

    # 按内容长度降序，大的先存盘
    sorted_by_size = sorted(
        tool_indices,
        key=lambda i: len(result[i].content),
        reverse=True,
    )
    for idx in sorted_by_size:
        if total_chars <= batch_threshold:
            break
        # 已存盘的跳过
        if result[idx].content.startswith("[spilled tool_result"):
            continue
        tool_name, payload = _parse_tool_result(result[idx])
        if tool_name is None:
            continue
        digest = _digest(payload)
        if digest in seen:
            result[idx] = _make_reread_msg(result[idx], tool_name, payload)
            total_chars -= len(result[idx].content)
            continue
        file_path = _save_to_disk(spill_dir, payload)
        seen.add(digest)
        spilled_paths.append(file_path)
        result[idx] = _make_preview_msg(result[idx], tool_name, file_path, payload)
        total_chars -= len(payload)

    return SpillResult(messages=result, spilled_paths=spilled_paths)


def _find_tool_results(messages: list[Message]) -> list[int]:
    """找出所有工具结果消息的索引（原生 role="tool" + 旧版用户消息格式）"""
    return [
        i for i, m in enumerate(messages)
        if m.role == "tool"
        or (m.role == "user" and m.content.startswith("[tool_result from "))
    ]


def _parse_tool_result(m: Message) -> tuple[str | None, str]:
    """解析工具结果消息

    Returns:
        (tool_name, payload)；非工具结果消息返回 (None, content)
    """
    if m.role == "tool":
        return m.name or "tool", m.content
    match = _TOOL_RESULT_RE.match(m.content)
    if not match:
        return None, m.content
    return match.group(1), m.content[match.end():]


def _digest(payload: str) -> str:
    """内容指纹 —— 用于"同一份内容只溢写一次"的记账"""
    return hashlib.sha1(payload.encode("utf-8", errors="replace")).hexdigest()


def _save_to_disk(spill_dir: Path, payload: str) -> str:
    """将负载写入磁盘文件，返回绝对路径"""
    file_name = f"spill_{uuid.uuid4().hex[:8]}.txt"
    file_path = spill_dir / file_name
    file_path.write_text(payload, encoding="utf-8")
    return str(file_path.resolve())


def _make_preview_msg(
    original: Message,
    tool_name: str,
    file_path: str,
    payload: str,
) -> Message:
    """构造预览消息：截断内容 + 文件路径

    明确劝止"整文件重读"，否则模型会照着提示把溢写文件再读一遍，
    读回来还是超阈值，于是触发新一轮溢写。

    原生 role="tool" 消息溢写后仍保留 role/tool_call_id/name，
    以维持 OpenAI 协议的 assistant.tool_calls ↔ tool 配对。
    """
    preview = payload[:PREVIEW_CHARS]
    if len(payload) > PREVIEW_CHARS:
        preview += f"\n\n... (截断，共 {len(payload)} 字符)"

    content = (
        f"[spilled tool_result from {tool_name}] "
        f"完整输出已保存到文件（共 {len(payload)} 字符），对话中只保留预览。\n"
        f"文件路径: {file_path}\n"
        f"注意: 不要用 read_file 整文件重读（会再次超阈值并被再次溢写）。{_SLICE_HINT}。\n"
        f"预览:\n{preview}"
    )
    if original.role == "tool":
        return Message(
            role="tool",
            content=content,
            tool_call_id=original.tool_call_id,
            name=tool_name,
        )
    return Message(role="user", content=content)


def _make_reread_msg(original: Message, tool_name: str, payload: str) -> Message:
    """模型重读了已溢写的内容 —— 硬拦截，不再新增溢写文件"""
    preview = payload[:PREVIEW_CHARS]
    content = (
        f"[spilled tool_result from {tool_name}] "
        f"这段内容（共 {len(payload)} 字符）此前已经溢写过并给出过预览，"
        f"现在不再重复溢写。\n"
        f"请停止整文件重读。{_SLICE_HINT}。\n"
        f"如果要汇报结论，请直接基于已有信息作答。\n"
        f"预览:\n{preview}"
    )
    if original.role == "tool":
        return Message(
            role="tool",
            content=content,
            tool_call_id=original.tool_call_id,
            name=tool_name,
        )
    return Message(role="user", content=content)
