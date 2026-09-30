# GXCode Ch04 Checklist — 结构化 System Prompt

- [ ] build(mode="act", tools=[...]) 返回含 7 个模块的 system prompt
- [ ] 新增模块只需定义函数并加入列表
- [ ] 连续两次 build() 返回相同字符串
- [ ] edit_file description 和全局指令同时含"必须先 read_file"
- [ ] /remind 后历史中出现 [SYSTEM_REMINDER] 消息
- [ ] Plan Mode 首轮完整，每 3 轮简短提醒
- [ ] Ch03 调用方式不变
- [ ] 所有模块导入不报错