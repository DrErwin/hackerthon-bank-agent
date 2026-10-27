# v05-frontend-demo-reset/01：正式管理重置入口

Ticket ID: v05-frontend-demo-reset/01
Package: [v05-cross-linkage/packages/04-frontend：页面体验](../../v05-cross-linkage/packages/04-frontend.md)，主代理 B26 后继分派
Spec: [B26 管理重置前端](../spec.md)
Type: 开发
Owner: Erwin（v0.5）；执行 frontend_acceptance 子代理
Directory: frontend/
Status: implemented_pending_review
Blocked by: None（公共模型 PR #326 已合；[PR #329：F30—F32 API 协调](https://github.com/DrErwin/hackerthon-bank-agent/pull/329) 已合入 87e30a94）
Core scenarios: [R01—R06](../spec.md#user-stories--核心场景)
Verification: 管理页 HTTP 边界交互测试、现有前端回归、真实 API/contract-demo 两构建；浏览器恢复后再由根代理安排真实 B26 联调
Branch: codex/v05-frontend-demo-reset-01

## 交付与验收

- [x] 仅已识别的独立管理员会话显示入口；普通用户无重置入口。
- [x] F30 使用原 request_id + 会话轮次，完整显示实际 effects；再次确认前无 F31。
- [x] F31 前保存原 request_id + reset_confirmation_id；重置中/部分失败/未知保留原请求和管理号，重复点击不创建新重置。
- [x] F32 只读查询，继续仅重用原 F31；刷新不自动发送重置。
- [x] 只有整体 succeeded 才显示新轮和重新进入用户页；旧轮管理员不能再次建立重置预览。
- [x] 局部测试、受影响回归及两构建有实际结果；[验证记录](../verification.md)。截图/200%/读屏/真机另记未验证。
- [ ] 根代理独立两轴审查及后续真实集成验收。

## Comments

2026-10-27：已领取本独立后继票，不混入 frontend-design-system/04 或 PR #321。当前仅离线实施，遵守浏览器安全停止。
