# 安全底座 AI 开发规则

本目录长期归 Ringo。v0.3 首条纵向路径由 Erwin 按根目录 `AGENTS.md` 的临时安排实现最小安全门，Ringo 负责评测与安全审查；阶段收口后维护回到 Ringo。开工读[安全底座原则](../../../docs/principles/02-security-platform.md)、[Review 与合并原则](../../../docs/principles/03-review-and-merge.md)及本目录 `README.md`。

- 只在本目录实现权限策略、统一执行器和确认门。审计与记忆的安全规则由 Ringo 定，`audit/`、`memory/` 的实现由 Erwin 在各自目录完成。
- 一次 PR 只改一类安全规则；写清谁会被放行或拦截、受影响模块及切换时点。影响公共字段时先走[公共改动流程](../../../docs/principles/03-review-and-merge.md#公共底座与-api-改动)。
- 工具未声明权限或副作用、越权、确认参数改变时默认拒绝。提交前验证放行、拒绝、参数改变和暂停恢复，并确认审计记录可追溯。
- 业务 PR 涉及权限、确认、资金执行、隐私或审计规则时，由 Ringo 审查；业务流程仍由模块负责人实现。
