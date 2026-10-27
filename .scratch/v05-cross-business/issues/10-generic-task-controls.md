# v05-cross-business/10：父计划通用继续与查询适配

Ticket ID: v05-cross-business/10
Package: [v05-cross-linkage/packages/03-cross：三个生活目标编排](../../v05-cross-linkage/packages/03-cross.md)
Spec: [通用任务操作最小规格](../generic-controls-10.md)
Type: 开发
Owner: Erwin（v0.5 统一负责）
Directory: `backend/app/modules/cross/`
Status: in_progress
Blocked by: None（API F11/F13 已发布，父计划消费缺口）
Accepted by: 本对话 AI，依据 2026-10-27 用户完成非比赛资料任务授权及中控委派
Accepted at: 2026-10-27
Core scenarios: XL-S01 退订后父计划继续、XL-X 暂停/原号恢复；核查养老金同类入口
Verification: 无模型调用的隔离 ASGI HTTP 红绿；不写原失败库，不改写历史模型失败证据；菜单/确认/未知原操作/取消单列。

## Comments

- 2026-10-27：中控将本票优先于会话恢复09；独立分支 `codex/v05-cross-generic-controls`，基线 `695ce6e5`。原 S01 失败批次由中控保存，本票只读备份后复现，不混入09安全接缝。
