# GXCode Ch03 Checklist — Agent Loop

> 每一项通过运行代码或观察行为来验证。

## 功能验收

- [x] 输入"创建 hello.py 写入 print('hello')，运行它"，Agent 自动 write_file → run_command → 回复结果
- [ ] 输入"读一下 README.md"，Agent 调用 read_file 后分析
- [ ] 纯聊天"你好"，一轮回复，不进入工具循环
- [ ] max_iterations=2，第 2 轮强制停止，显示"达到迭代上限"
- [ ] Ctrl+C 两次，循环退出，显示"已取消"
- [ ] 移除所有工具，连续 3 次失败停止，显示"连续工具错误"
- [ ] TUI 显示 `[迭代 1/25]`、`[工具]`、`[结果]` 标签
- [ ] StreamCollector 同时推送 UI 并累积完整响应
- [x] 一次请求两个 read_file 并发执行
- [ ] 同时读写任务，读并发、写串行
- [ ] `/plan` 只用只读工具，输出计划。`/do` 后全工具
- [ ] 对话历史第一条 role=system
- [ ] 不启用 Agent Loop 时与 Ch02 一致

## 编译与运行

- [ ] `gxcode` 启动正常
- [ ] 所有模块导入不报错
