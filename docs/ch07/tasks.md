# GXCode Ch07 Tasks — 双层上下文压缩

## T1: Provider 捕获 Usage
- openai.py: stream_options + UsageEvent 产出
- anthropic.py: message_start/message_delta/message_stop 累积产出

## T2: StreamCollector 携带 Usage
- collector.py: 捕获 UsageEvent → TurnResult.usage

## T3: Token 估算器
- token_counter.py: 锚定 API usage + 增量 chars/4 估算

## T4: 轻量预防
- file_spill.py: 单条/批量工具结果超阈值存盘，预览+路径留对话

## T5: 重量兜底
- summarizer.py: LLM 结构化摘要，草稿→正式，禁止调工具，熔断

## T6: ContextManager 编排
- manager.py: 每次 API 请求前两层检查 + 锚定
- session.py: + replace_history()

## T7: 配置 + 集成
- config.py: ContextConfig + YAML context 节解析
- agent/loop.py: LLM 调用前检查 + 调用后锚定
- tui/app.py: 传递 context_manager
- main.py: 初始化上下文组件（双 Provider）

## T8: 文档
- docs/ch07/spec.md: 功能规格
- docs/ch07/plan.md: 架构设计
- docs/ch07/checklist.md: 验收清单
- gxcode.yaml.example: context 节示例