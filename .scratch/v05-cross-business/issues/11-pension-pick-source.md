# v05-cross-business/11：养老金退订选择页真实来源说明

Ticket ID: v05-cross-business/11
Package: [v05-cross-linkage/packages/03-cross：三个生活目标编排](../../v05-cross-linkage/packages/03-cross.md)
Spec: [票11最小规格](../pension-source-11.md)
Type: 开发
Owner: Erwin（v0.5）；执行 frontend_acceptance 子代理
Directory: backend/app/modules/cross/
Status: implemented_pending_review
Blocked by: None（前票10已随 PR #332 合入 main9b54d4e3）
Accepted by: Erwin，通过用户非比赛资料任务授权与中控明确分派
Accepted at: 2026-10-27
Core scenarios: XL-P01 前置退订选择页；PS01—PS03 见最小规格
Verification: 既有养老金相关定向检查及减支失败说明单例；根代理真实 HTTP 前置页复核新文案。无新增文案镜像测试，不跑完整127项。
Branch: codex/v05-cross-pension-source-11

## 验收

- [x] 养老金选择页说明签约清单真实来源，不把未计划的账单比较说成查询中。
- [x] 减支账单比较/失败/等待说明保留；仅文案分支变化，业务不变。
- [x] 必要既有检查 17 passed，差异空白通过；[局部结果](../pension-source-11.md#实际局部结果2026-10-27)。
- [ ] 根代理独立两轴和真实 HTTP 前置页文案复核。

## Comments

2026-10-27：复用前票已合入的干净 managed 工作树；从最新 main9b54d4e3 开独立分支，不覆盖原分支或平台13工作树。
