# 01：未提交风险覆盖暂停保留原任务修改和取消

Ticket ID: v05-transfer-pause-recovery/01
Package: [v05-cross-linkage/packages/01-platform-bank](../../v05-cross-linkage/packages/01-platform-bank.md)
Spec: [提交前风险证据暂停的原任务恢复](../spec.md)
Core scenarios: PR01—PR08
Type: 开发
Owner: Erwin（v0.5）；执行 transfer_pause_recovery AI 子代理
Directory: backend/app/modules/transfer/
Status: merged_ui_verified — PR356 / 17f7ef2c
Blocked by: None（既有输入、草稿修订与安全确认接缝可用）
Accepted by: 根明确委派，依据本轮用户完成非比赛资料及真实页面走查授权
Accepted at: 2026-10-29
Branch: codex/v05-transfer-pause-recovery-01
Verification: 先复现真实Workflow原红，再做定向、受影响transfer及Harness回归。记录源码、XML/hash与替身边界，不操作根正在运行的银行。

- [x] 原红可重复捕捉原任务无修改或取消动作。
- [x] 明确提交前风险覆盖缺失可以原任务修改、重核对或取消。
- [x] 缺失事实不放行；新资金参数必须新操作/修订和重新确认验证。
- [x] 执行复用、未知/处理中、权限/会话、冲突和高风险边界回归通过。
- [x] [固定源红绿及108项必要组合](../verification.md)交付；作者不自合并，不写真人接受。
- [x] 两位非作者独立Standards/Spec均0必须项，CI精确head因账号计费未启动；根已合入PR356（17f7ef2c）。
- [x] [原页面复验](../../v05-control/ui-walkthrough-2026-10-29/walkthrough.md)：同任务恢复可编辑/取消，未批准A5仍暂停，旧任务明确取消无银行写；新500元经完整门成功并刷新无重复。额外话语不扩大演示事实范围，非真人接受。
