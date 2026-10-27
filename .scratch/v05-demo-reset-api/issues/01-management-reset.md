# v05-demo-reset-api/01：管理二次确认与整体重置原号协调

Ticket ID: v05-demo-reset-api/01
Package: [公共平台与银行](../../v05-cross-linkage/packages/01-platform-bank.md)
Spec: [规格](../spec.md)
Type: 开发
Owner: Erwin
Directory: `backend/app/api/`
Status: in_progress
Accepted by: Erwin，主代理明确分派
Accepted at: 2026-10-27
Blocked by: PR #322；services 网关排空与平台票12为整体装配前置，API先按公开接缝实现
Core scenarios: M01—M06，见规格
Verification: 临时库的真实 API HTTP 与银行/记忆事实、原管理号恢复、身份与轮次拒绝；不运行共享库、浏览器或真实模型。

## 交付

- [ ] F25 当前演示视图，F30 预览/二次确认，F31 持久原号重置，F32 只读查询。
- [ ] 停收与在途排空，分阶段失败/重启恢复，银行原号查询、记忆预置和时钟恢复，全部完成后才发布新轮与成功。
- [ ] 旧用户会话和授权不可进入新轮，独立管理身份仍可查询原管理号和历史审计。
- [ ] 必要定向及受影响 API 验证、独立两轴审查、PR 回交；整体平台/服务装配与真人接受分别记录。
