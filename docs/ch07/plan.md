# GXCode Ch07 Plan — 双层上下文压缩

## 架构

```
context/
├── token_counter.py    ← 近似 Token 估算（锚定 + 增量字符）
├── file_spill.py       ← 轻量预防（工具结果超阈值存盘）
├── summarizer.py       ← 重量兜底（LLM 生成结构化摘要）
├── manager.py          ← 编排器（每次 API 请求前两层检查）
└── __init__.py
```

## 核心接口

```python
class TokenCounter:
    def set_anchor(messages, usage)     # 记录 API 准确用量
    def estimate(messages) -> int       # 估算当前 token 数

class Summarizer:
    def __init__(provider, model, max_failures)
    async def compress(messages, counter, keep_tokens, keep_min) -> CompressResult

class ContextManager:
    def __init__(session, counter, summarizer, config)
    async def check_and_compress_async(auto=True) -> CompressResult
    def set_anchor(messages, usage)
```

## 技术决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| Token 估算 | 锚定 API usage + 增量 chars/4 | 不引入精确 tokenizer 依赖 |
| 溢写格式 | `[spilled tool_result]` 前缀 + 路径 | 模型能识别并重新读取 |
| 摘要 Provider | 单独创建不带 tools 的实例 | 防止摘要 LLM 误调工具 |
| 熔断 | 连续 3 次失败 | 避免摘要死循环 |
| 安全余量 | auto=13K, manual=3K | 自动触发保守，手动触发激进 |
| 分割策略 | 尾部回溯 ~10K token 且 >= 5 条 | 保证近期上下文完整性 |
| 上下文配置 | ContextConfig 定义在 config.py | 避免循环导入（config -> context -> session -> provider -> config） |