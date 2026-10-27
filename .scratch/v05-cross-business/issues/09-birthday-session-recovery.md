# v05-cross-business/09：生日敏感等待的新会话恢复

Ticket ID: v05-cross-business/09
Package: [v05-cross-linkage/packages/03-cross：三个生活目标编排](../../v05-cross-linkage/packages/03-cross.md)
Spec: [联动业务规格](../spec.md)，[安全依赖与失败证据](../session-recovery-09.md)
Type: 开发
Owner: Erwin（v0.5 统一负责）
Directory: `backend/app/modules/cross/`
Status: in_progress — 先保存真实失败；安全提供接缝前不宣称冻结验证阶段恢复闭环
Blocked by: [v05-birthday-platform-dependencies/10：G3 会话恢复 provider](../../v05-birthday-platform-dependencies/issues/10-g3-session-recovery.md)（PR #323）；旧会话 pending_freeze 安全处置接缝由中控另派安全目录票
Accepted by: 本对话 AI，依据 2026-10-27 用户完成非比赛资料任务授权及中控委派
Accepted at: 2026-10-27
Core scenarios: XL-B 敏感等待恢复、XL-X 会话/权限与重复执行
Verification: 真实 Harness/Cross/存储/安全/模拟银行，规划器为明示替身；旧卡拒绝、新会话新版本、旧挑战不复用，未知沿原号核实。局部组合不写作真实模型/页面/真人安全验收。

## What to build

生日冻结、下单、核销的确认/验证等待恢复应从本模块 SOP 重查当前安全门，不回缓存旧会话卡。新会话必须新确认/验证；不能在平台篡改 Cross 私有状态，不能移除安全限定授权的唯一性与身份检查。

已执行或未知仍核实原操作；不能盲换 operation、重冻或退款。未提交且安全证明可撤离时，消费安全方明确的退休/新尝试接缝。

## Comments

- 2026-10-27：中控安排本票在平台票12之后完成；先以真实组合保存冻结旧卡与限定授权冲突失败，安全最小接口需求另文，未修改安全状态规则。
