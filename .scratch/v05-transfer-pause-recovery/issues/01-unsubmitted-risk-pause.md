# 01：未提交风险覆盖暂停保留原任务修改和取消

Ticket ID: v05-transfer-pause-recovery/01
Package: [v05-cross-linkage/packages/01-platform-bank](../../v05-cross-linkage/packages/01-platform-bank.md)
Spec: [提交前风险证据暂停的原任务恢复](../spec.md)
Core scenarios: PR01—PR07
Type: 开发
Owner: Erwin（v0.5）；执行 transfer_pause_recovery AI 子代理
Directory: backend/app/modules/transfer/
Status: in_progress
Blocked by: None（既有输入、草稿修订与安全确认接缝可用）
Accepted by: 根明确委派，依据本轮用户完成非比赛资料及真实页面走查授权
Accepted at: 2026-10-29
Branch: codex/v05-transfer-pause-recovery-01
Verification: 先复现真实Workflow原红，再做定向、受影响transfer及Harness回归。记录源码、XML/hash与替身边界，不操作根正在运行的银行。

- [ ] 原红可重复捕捉原任务无修改或取消动作。
- [ ] 明确提交前风险覆盖缺失可以原任务修改、重核对或取消。
- [ ] 缺失事实不放行；新资金参数必须新操作/修订和重新确认验证。
- [ ] 执行复用、未知/处理中、权限/会话、冲突和高风险边界不扩大。
- [ ] 局部红绿与精确来源交付；作者不自合并，不写真人接受。
