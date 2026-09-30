# GXCode Ch09 Spec — 命令系统

## 背景

当前所有用户输入都送入 Agent，包括清屏、查状态等非对话操作。需要一套斜杠命令机制，绕过 LLM 直接执行，快、省 Token、行为确定。

## 目标

- 命令注册中心 + 解析器 + 分发器，斜杠开头的输入走本地命令
- 启动时检测别名冲突，撞名 panic 退出
- 三层抽象：命令元数据 / 界面控制接口 / 分流器
- 内置 10 个高频命令
- Tab 补全（单匹配直补、多匹配菜单），隐藏命令不参与

## 功能需求

- **F1: 注册中心** — 登记命令元数据（name/aliases/desc/usage/type/param_hint/handler/hidden），启动阶段检测别名冲突（包括跨命令 name 与别名），冲突直接 sys.exit。
- **F2: 解析器** — 识别 `/` 前缀，第一个空格前为命令名（转小写），之后为参数字符串。空输入早返回 None，未命中返回提示信息含 `/help`。
- **F3: 三模式命令** — local（纯本地无副作用）、ui（影响界面状态）、prompt（注入预设提示词到对话）
- **F4: 界面控制接口** — UIController 抽离 add_message / send_user_message / set_mode / get_token_usage / refresh_status 五个方法，命令不直接绑定 Textual widget。
- **F5: 分流器** — 在 `on_input_submitted` 入口判断，以 `/` 开头走命令分发，否则送入 Agent。
- **F6: Tab 补全** — 单匹配直补命令名，多匹配弹下拉菜单让用户选。hidden=True 的命令不参与补全。
- **F7: 10 个内置命令** — `/help /compact /clear /plan /do /session /memory /permission /status /review`

## 非功能需求

- **N1:** 命令注册时别名冲突检测 O(n²) 可接受（命令数 < 100）
- **N2:** 本地命令响应 < 5ms
- **N3:** 无新外部依赖

## 不做的事

- 用户自定义命令、动态生成提示词、命令级权限控制（留给 Skill 系统）

## 验收标准

- **AC1:** 别名冲突启动时 panic 退出
- **AC2:** `/help` 列出所有可见命令
- **AC3:** `/clear` 清空聊天区域
- **AC4:** `/plan` 切换到计划模式，`/do` 切回执行模式
- **AC5:** 非斜杠输入正常送给 Agent
- **AC6:** Tab 补全单匹配直补，多匹配弹菜单
- **AC7:** 未识别命令提示 `/help`