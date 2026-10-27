# v05-demo-reset-api/01：管理二次确认与整体重置原号协调

Ticket ID: v05-demo-reset-api/01
Package: [公共平台与银行](../../v05-cross-linkage/packages/01-platform-bank.md)
Spec: [规格](../spec.md)
Type: 开发
Owner: Erwin
Directory: `backend/app/api/`
Status: implemented_pending_review — 11项API定向通过，待最终依赖基线、完整API回归及独立两轴审查
Accepted by: Erwin，主代理明确分派
Accepted at: 2026-10-27
Blocked by: PR #322 / #325 / #326 及平台票12，最终PR需整理为纯API差异
Core scenarios: M01—M06，见规格
Verification: 临时库的真实 API HTTP 与银行/记忆事实、原管理号恢复、身份与轮次拒绝；不运行共享库、浏览器或真实模型。

## 交付

- [x] F30 预览/二次确认，F31 持久原号重置，F32 只读查询；F25/F29不在本票。
- [x] 停收与在途排空，分阶段失败/重启恢复，银行原号查询、记忆预置和时钟恢复，全部完成后才发布新轮与成功。
- [x] 旧用户会话和授权不可进入新轮，独立管理身份仍可查询原管理号和本人来源轮次历史审计；旧轮导出保持原拒绝。
- [ ] 必要定向及受影响 API 验证、独立两轴审查、PR 回交；整体平台/服务装配与真人接受分别记录。
