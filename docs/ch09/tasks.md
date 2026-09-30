# GXCode Ch09 Tasks — 命令系统

## T1: 命令注册中心 + 解析器
- registry.py: Command 数据类 + CommandRegistry（冲突检测）
- parser.py: 斜杠识别 + 命令名/参数分离

## T2: 界面控制接口
- controller.py: UIController ABC（5 个方法）

## T3: 分流器 + 分发器
- dispatcher.py: 判断斜杠 vs AI，路由到命令或 Agent

## T4: 10 个内置命令
- builtin/: help/clear/compact/plan/do/session/memory/permission/status/review

## T5: Tab 补全
- completion.py: 单匹配直补、多匹配菜单

## T6: 集成到 TUI
- tui/app.py: 接入 dispatcher，替换现有内联命令处理
- tui/input_bar.py: 接入 completion

## T7: 文档
- docs/ch09/: spec/plan/checklist/tasks