# v05-cross-business/10：父计划通用继续与查询适配

Ticket ID: v05-cross-business/10
Package: [v05-cross-linkage/packages/03-cross：三个生活目标编排](../../v05-cross-linkage/packages/03-cross.md)
Spec: [通用任务操作最小规格](../generic-controls-10.md)
Type: 开发
Owner: Erwin（v0.5 统一负责）
Directory: `backend/app/modules/cross/`
Status: ready_for_review — Spec P2补修红转绿，含API329的main组合Cross127 passed（7HTTP）；待原Spec限定复审及中控合入
Blocked by: None（API F11/F13 已发布，父计划消费缺口）
Accepted by: 本对话 AI，依据 2026-10-27 用户完成非比赛资料任务授权及中控委派
Accepted at: 2026-10-27
Core scenarios: XL-S01 退订后父计划继续、XL-X 暂停/原号恢复；核查养老金同类入口
Verification: 无模型调用的隔离 ASGI HTTP 红绿；不写原失败库，不改写历史模型失败证据；菜单/确认/未知原操作/取消单列。

## Comments

- 2026-10-27：中控将本票优先于会话恢复09；独立分支 `codex/v05-cross-generic-controls`，基线 `695ce6e5`。原 S01 失败批次由中控保存，本票只读备份后复现，不混入09安全接缝。
- 2026-10-27：同步压缩合入后的 main `e4f0fe50`，只重放本票（`b1f11f93`，本票 patch 等价），[实际证据](../generic-controls-10.md#最新主线组合验证)。仅剩独立审查/远端状态与中控合入，不标真人接受。
- 2026-10-27：中控委派API重置子代理临时接手Spec P2补修，原作者继续独立平台13。本地 `781b8eb7/6a7d309d` 已基于含API329的main `dcbf6144`，与原 `b1f11f93/a473a985` 的range-diff两项均为`=`。既定验证接缝为真实ASGI HTTP：首笔转账真实提交但响应丢失→父取消→沿原子任务查询成功→F11；期望无第二笔子任务、部分完成且后续停止、原资金安排解除。仅Cross与本组材料，不改API/平台/安全。
- 2026-10-27：P2补修检查点 `481d8118`，目标HTTP先1 failed/22.59s，后1 passed/19.60s；完整Cross127 passed/164.26s/exit0，含原6HTTP与新增1HTTP。原126与模型失败/只读回放资料保留；[补修与原始证据](../generic-controls-10.md#spec-p2叫停后只核实收尾)。账单对比文案/来源缺口留给独立Cross11，本票不混入。
