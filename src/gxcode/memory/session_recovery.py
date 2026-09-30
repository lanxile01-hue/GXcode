"""GXCode 会话恢复逻辑

处理四类异常后返回可用的消息列表：
1. 孤儿工具调用 → 截断到最后一个完整配对
2. token 超限 → 标记需要压缩
3. 长时间跨度 → 插入时间提醒
4. 坏行 → 调用方已跳过（JSONDecodeError）
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta

# 超过此时间差插入提醒
_GAP_THRESHOLD_HOURS = 24


@dataclass
class RecoveryResult:
    """恢复结果"""
    entries: list[dict]
    truncated: bool = False        # 是否因孤儿工具调用被截断
    needs_compress: bool = False   # 是否 token 超限需要压缩


def recover_session(
    entries: list[dict],
    max_chars: int = 600_000,      # 约 150K tokens（chars/4）
) -> RecoveryResult:
    """从 JSONL 行列表恢复可用消息

    Args:
        entries: 原始 JSONL 行（已跳过坏行）
        max_chars: 字符数上限，超出标记 needs_compress

    Returns:
        RecoveryResult: 恢复后的条目 + 状态标记
    """
    if not entries:
        return RecoveryResult(entries=[], truncated=False, needs_compress=False)

    result = list(entries)
    truncated = False

    # ── 1. 孤儿工具调用截断 ──
    # 从尾部找最后一个 "完整的" 位置
    safe_cut = len(result)
    for i in range(len(result) - 1, -1, -1):
        entry = result[i]
        if entry.get("role") == "assistant" and entry.get("tool_calls"):
            # assistant 带了 tool_calls，检查后面有没有 tool_result
            has_result = False
            for j in range(i + 1, len(result)):
                if result[j].get("role") == "tool_result":
                    has_result = True
                    break
            if not has_result:
                safe_cut = i
        elif entry.get("role") in ("user", "system", "tool_result"):
            # 安全点：可以从这儿以前保留
            safe_cut = i + 1
            break
        elif entry.get("role") == "assistant":
            # assistant 无 tool_calls → 安全
            safe_cut = i + 1
            break

    if safe_cut < len(result):
        result = result[:safe_cut]
        truncated = True

    if not result:
        return RecoveryResult(entries=[], truncated=True, needs_compress=False)

    # ── 2. 时间跨度提醒 ──
    result = _insert_gap_reminders(result)

    # ── 3. token 超限检查 ──
    total_chars = sum(len(e.get("content", "")) for e in result)
    needs_compress = total_chars > max_chars

    return RecoveryResult(
        entries=result,
        truncated=truncated,
        needs_compress=needs_compress,
    )


def _insert_gap_reminders(entries: list[dict]) -> list[dict]:
    """在长时间间隔处插入提醒消息"""
    result: list[dict] = []
    for i, entry in enumerate(entries):
        if i > 0:
            ts_prev = entries[i - 1].get("timestamp", "")
            ts_curr = entry.get("timestamp", "")
            if ts_prev and ts_curr:
                try:
                    t_prev = datetime.fromisoformat(ts_prev)
                    t_curr = datetime.fromisoformat(ts_curr)
                    delta = t_curr - t_prev
                    if delta > timedelta(hours=_GAP_THRESHOLD_HOURS):
                        hours = int(delta.total_seconds() / 3600)
                        result.append({
                            "role": "system",
                            "content": (
                                f"[系统提醒] 距离上一条消息已过去约 {hours} 小时"
                                f"（{_fmt_time(t_prev)} → {_fmt_time(t_curr)}），"
                                "上下文可能有断档，请基于现有信息继续。"
                            ),
                            "timestamp": ts_curr,
                        })
                except (ValueError, TypeError):
                    pass
        result.append(entry)
    return result


def _fmt_time(dt: datetime) -> str:
    return dt.strftime("%m-%d %H:%M")