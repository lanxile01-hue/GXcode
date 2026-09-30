# GXCode Checklist — 纯对话 CLI

> 每一项通过运行代码或观察行为来验证，聚焦系统行为。

## 功能验收

- [ ] 准备含 2 个供应商的 YAML 配置，启动后 A 供应商正常调用（验证：发送"你好"，观察到流式回复）
- [ ] 编辑配置切换 `active` 为 B 供应商，重启后 B 供应商正常调用（验证：发送"你好"，观察到流式回复）
- [ ] Anthropic 配置 `thinking: true`，请求中携带 `thinking` 参数（验证：抓包或日志确认请求体包含 thinking 字段）
- [ ] OpenAI 配置 `thinking: true`，请求中不携带 thinking 参数（验证：抓包或日志确认请求体不含 thinking 字段）
- [ ] TUI 启动后显示对话区和输入区（验证：肉眼观察界面布局完整）
- [ ] 连续发送 3 条消息，AI 的第 3 条回复能引用第 1 条内容（验证：先问"我叫小明"，再闲聊，再问"我叫什么"，期望回复提及"小明"）
- [ ] 长回复逐字出现在对话区（验证：问一个需要长回答的问题，观察字母逐个出现）
- [ ] Anthropic 供应商发送"你好"收到流式回复（验证：肉眼观察流式输出正常）
- [ ] OpenAI 供应商发送"你好"收到流式回复（验证：肉眼观察流式输出正常）
- [ ] Anthropic thinking 模式下，对话区显示 `[思考]` 前缀内容，随后显示正文（验证：问复杂问题，观察 thinking 折叠/标记展示）

## 扩展性验收

- [ ] 新增 MockProvider（返回 "hello from mock"），不改动 TUI 代码即可使用（验证：切换配置到 mock provider，启动后发送任意消息，看到固定回复）
- [ ] 传入无效 protocol 时，`create_provider` 抛出明确异常（验证：`protocol: "invalid"` 后启动，看到可读错误信息）

## 健壮性验收

- [ ] 无效 API Key 时界面显示可读错误，不崩溃（验证：故意用错误 key，输入消息后看到错误提示而非 Traceback）
- [ ] 配置文件缺失时启动失败并提示（验证：`gxcode --config /nonexistent.yaml`，看到清晰错误信息）
- [ ] 配置缺少必填字段时启动失败并提示（验证：删除 `api_key` 字段后启动，看到提示信息）

## 编译与运行

- [ ] `pip install -e .` 成功，无报错（验证：`gxcode --help` 正常输出）
- [ ] 所有模块导入不报错（验证：`python -c "import gxcode; import gxcode.config; import gxcode.provider; import gxcode.session; import gxcode.tui"`）