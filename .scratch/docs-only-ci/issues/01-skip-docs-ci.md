# 01：纯文档PR与主线提交跳过CI

Ticket ID: docs-only-ci/01
Package: [transfer-agent-framework/packages/01-vertical-backend：底座工作线](../../transfer-agent-framework/packages/01-vertical-backend.md)（本票为项目负责人直接授权的共享CI维护，不新增业务验收结论）
Spec: [纯文档跳过CI](../spec.md)
Type: 开发 / CI配置
Owner: Erwin
Directory: .github/workflows/
Status: resolved
Blocked by: 无
Accepted by: 项目负责人于2026-10-04明确指示“改GitHub配置啊”；Codex代执行

## 验收

- Markdown/reST及约定docs图示资源的纯文档PR和main推送不运行Repository checks。
- 文档混入代码、依赖、工作流、执行配置仍运行原检查。
- main分支限制、job/权限/测试步骤不变，变更仅一个目录。
- YAML、代表路径分类与配置PR CI通过，经审查合入GitHub main；如实区分本次配置CI与未来纯文档跳过。

## Comments

- 2026-10-04：用户明确要求实际更改GitHub配置。复用干净独立worktree，从origin/main建立codex/skip-docs-ci；不覆盖主工作区。

- 2026-10-04 交付：配置提交`165ccb8`，独立AI Standards/Spec均0阻合入问题；YAML及14组文档/混合/代码/执行配置路径分类通过。main分支当前protected=false且required checks为空，路径跳过不会形成现有强制CI合并门槛。PR #49已按用户更改GitHub配置授权squash合入`fd6c677fcbdef286d303f2eed5d8f4b3fe3898ba`；PR CI与主线CI均通过。已通过GitHub contents API逐字节核对main工作流，PR/main两个过滤生效于已发布配置；其余job、权限和分支条件未改变。主线CI：https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/37136716947 。本机工作流与AGENTS记录已同步，其他未提交改动保留。维护票resolved，不改变v0.3业务验收状态。
