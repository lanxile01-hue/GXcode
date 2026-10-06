# GXCode Ch05 Checklist — 权限系统

- [x] rm -rf / 被黑名单拦截
- [x] echo hello 正常执行
- [x] ../../etc/passwd 沙箱拦截
- [x] ./README.md 正常读取
- [x] Bash(git *): allow + Bash(rm *): deny 规则生效
- [x] /permission strict 后写文件需确认
- [x] /permission permissive 后写文件直接执行
- [ ] 确认框 deny 后 Agent Loop 继续
- [x] 会话规则覆盖项目规则
- [ ] 无规则时与 Ch04 一致
