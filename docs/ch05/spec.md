# GXCode Ch05 Spec — 五层防御权限系统

## 背景

当前模型可自由执行命令和文件操作。需装防护：拦截危险命令、限制文件范围、给用户控制权。权限拒绝时 Agent 不崩溃，让模型调整策略。

## 目标

- 五层防御：黑名单 → 沙箱 → 规则引擎 → 权限模式 → 人在回路
- 黑名单不可配置，正则拦截高危命令
- 路径沙箱限制文件操作在项目目录内
- 规则引擎按 工具名(模式) 格式声明 allow/deny
- 四档权限模式：strict/default/permissive/custom
- 人在回路：未命中规则时确认，三种放行级别

## 功能需求

- **F1: 黑名单** — 硬编码正则列表（rm -rf /、mkfs、dd if= 等），run_command 执行前匹配，不可配置放开。
- **F2: 路径沙箱** — 文件工具操作限制在项目根目录内，先 resolve() 再前缀判断。
- **F3: 可配置规则** — 规则格式 `工具名(模式): allow|deny`，支持精确和 glob 匹配。
- **F4: 权限模式** — `/permission strict|default|permissive|custom` 切换。
- **F5: 人在回路** — 规则未命中时弹确认框，允许 allow_once/allow_session/allow_always/deny。
- **F6: 规则优先级** — 三层 YAML（用户全局 < 项目级 < 会话临时），逐层判断。
- **F7: 拒绝不终止** — 权限拒绝返回 ToolResult(success=false)，Agent Loop 继续。

## 非功能需求

- **N1:** 权限检查 < 1ms
- **N2:** resolve() 防符号链接逃逸
- **N3:** 规则文件缺失不报错，格式错误跳过并日志
- **N4:** 未启用时与 Ch04 一致
- **N5:** 无新外部依赖

## 不做的事

- 网络请求限制、资源配额、审计日志、进程隔离、时间窗口限制

## 验收标准

- **AC1:** rm -rf / 被拦截，echo hello 正常
- **AC2:** ../../etc/passwd 被沙箱拦截
- **AC3:** git * allow + rm * deny 规则生效
- **AC4:** /permission strict/permissive 切换生效
- **AC5:** default 模式未命中规则弹确认框
- **AC6:** 会话规则覆盖项目规则
- **AC7:** 权限拒绝后 Agent Loop 不终止