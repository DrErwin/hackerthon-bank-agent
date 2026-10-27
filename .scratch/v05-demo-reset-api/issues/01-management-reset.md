# v05-demo-reset-api/01：管理二次确认与整体重置原号协调

Ticket ID: v05-demo-reset-api/01
Package: [公共平台与银行](../../v05-cross-linkage/packages/01-platform-bank.md)
Spec: [规格](../spec.md)
Type: 开发
Owner: Erwin
Directory: `backend/app/api/`
Status: implemented_pending_review — 最终组合API246项+平台时钟5项通过；Standards独立审查0必须项，待Spec审查及合入
Accepted by: Erwin，主代理明确分派
Accepted at: 2026-10-27
Depends on: PR #322 / #325 / #326 / #327 / #328；最终PR整理为纯API差异并核对受测树
Core scenarios: M01—M07，见规格
Verification: 临时库的真实 API HTTP 与银行/记忆事实、原管理号恢复、身份与轮次拒绝；不运行共享库、浏览器或真实模型。

## 交付

- [x] F30 预览/二次确认，F31 持久原号重置，F32 只读查询；F25/F29不在本票。
- [x] 停收与在途排空，分阶段失败/重启恢复，银行原号查询、记忆预置和时钟恢复，全部完成后才发布新轮与成功。
- [x] 旧用户会话和授权不可进入新轮，独立管理身份仍可查询原管理号和本人来源轮次历史审计；旧轮导出保持原拒绝。
- [x] 12项API重置定向与正式装配；正确依赖组合API246项+平台时钟5项完整验证，原始JUnit另存。
- [x] Draft [PR #329](https://github.com/DrErwin/hackerthon-bank-agent/pull/329) 回交并附当前任务；Standards独立审查0必须项。
- [ ] Spec独立审查及最终合入；真实模型/页面、真人安全与最终接受分别记录。
