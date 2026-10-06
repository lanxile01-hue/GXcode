# GXCode 本地评测

这套评测不调用真实模型，使用固定的 FakeProvider，保证结果可重复、无需 API Key。

运行：

```text
python evaluations/run_eval.py
```

当前覆盖 30 项测试，分为 11 类工程能力：

1. 危险命令和目录穿越拦截。
2. 会话级规则覆盖默认权限。
3. 超长工具结果溢出到磁盘，并保留预览。
4. JSONL 会话读写，以及损坏行跳过恢复。
5. Agent 单轮和多轮工具链闭环。
6. 安全工具并发执行耗时约束。
7. 上下文压缩的用户消息保留和边界提示。
8. 摘要失败熔断、Token 锚点增量估算。
9. MCP 结果适配、Skill 参数激活和命令解析。
10. 空转纠偏（模型只输出前摇旁白时必须继续迭代，且纠偏次数有上限）、
    子进程输出按系统编码解码、System Prompt 的同轮工具调用约束与环境信息注入。
11. 溢写防递归（同一份内容只溢写一次，重读溢写文件不再新增文件）
    与默认溢写阈值足以容纳常规源码文件。

## 验收清单核查

`verify_checklist.py` 把 docs/ch01~ch10 的 checklist 中可离线判定的条目编码成断言，
跑通后回填对应 checkbox，并生成 docs/CHECKLIST_STATUS.md：

```text
python evaluations/verify_checklist.py           # 只核查，不改动文档
python evaluations/verify_checklist.py --write   # 核查通过后回填勾选
```

当前 58 项通过离线核查。需要真实模型或人工观察的条目（端到端调用、TUI 渲染、
MCP 真实连接、LLM 笔记去重）保持未勾选，由人工确认。

结果会写入 `evaluations/latest_result.json`，包含通过状态、测试数量和耗时。这些是核心机制回归指标，不等同于 SWE-bench 或真实模型的修复成功率；后续接入真实模型时，应另建带固定任务集、成功标准和运行成本统计的评测。
