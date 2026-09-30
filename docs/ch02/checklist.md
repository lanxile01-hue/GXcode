# GXCode Ch02 Checklist — 工具系统

> 每一项通过运行代码或观察行为来验证。

## 功能验收

- [ ] 新增 MockTool 继承 Tool，注册到 registry，`to_api_schema()` 包含对应定义（验证：检查返回列表含 MockTool）
- [ ] `read_file` 读存在的文件返回内容；读不存在返回 `success=false`（验证：分别测试）
- [ ] `write_file` 自动创建父目录后写入，读取写入内容一致（验证：写 → 读 → 对比）
- [ ] `edit_file` 唯一匹配替换正确；old_string 不存在报"未找到"；出现多次报"匹配到 N 处"（验证：三种场景）
- [ ] `run_command("echo hello")` 返回 stdout 含 "hello"；`run_command("sleep 60")` 超时返回错误（验证：正常 + 超时）
- [ ] `glob_find("*.py")` 返回 .py 文件列表（验证：与 `dir *.py` 对比）
- [ ] `grep_search("def", ".")` 返回匹配行及文件路径（验证：确认含项目函数定义）
- [ ] `registry.to_api_schema()` 含六个工具，格式兼容 OpenAI/Anthropic（验证：检查 name/description/parameters 字段）
- [ ] 工具异常返回 ToolResult(success=false)，GXCode 不崩溃（验证：MockTool 抛异常）
- [ ] Provider 流式解析出完整 ToolCall（验证：真实 API 工具调用测试）
- [ ] 工具执行后 history 含 tool_use 和 tool_result（验证：`session.history` 检查）
- [ ] TUI 工具调用显示 `[工具]` 前缀，样式区分（验证：肉眼观察）
- [ ] `read_file("../../etc/passwd")` 被拒绝（验证：返回越权错误）
- [ ] 工具未激活时纯对话与第一章一致（验证：不传 tools，发送"你好"）

## 编译与运行

- [ ] 所有模块导入不报错（验证：`python -c "import gxcode.tools; ..."`）
- [ ] `gxcode` 启动正常，六个工具已注册