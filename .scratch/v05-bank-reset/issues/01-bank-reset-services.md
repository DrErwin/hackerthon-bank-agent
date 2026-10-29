# v05-bank-reset/01：受控原子银行重置与原号查询

Ticket ID: v05-bank-reset/01
Package: [v05-cross-linkage/packages/01-platform-bank](../../v05-cross-linkage/packages/01-platform-bank.md)
Spec: [银行重置规格](../spec.md)
Type: 开发
Owner: Erwin
Directory: `backend/app/services/`
Status: merged — PR #322 已合入 `aac4a5fb`；2026-10-29 核对。原验证与审查按各批记录，CI 计费未启动；实际结果与待接受项见[v0.5 完成情况](../../../docs/versions/v0.5.0/completion.md)。

原交付时状态（历史）：implemented_pending_review — 149 项 services/银行专项通过；待主代理两轴独立审查、PR 合入及整体接线。
Accepted by: Erwin，主代理本轮授权分派
Accepted at: 2026-10-27
Blocked by: None（服务内部接缝已由主代理确认；整体流程另依赖 API/平台）
Core scenarios: R01—R06，见规格
Verification: 新隔离 SQLite 的银行事实、失败回滚、在途等待、原号重放、旧轮拒绝及定向 services 回归；不是页面/模型或整体 B26 接受。

## 验收

- [x] 受控管理身份，绑定原/新轮次、起点和原管理操作；结果持久且可原号回查。
- [x] 在途 processing 不清；成功重放不重复重置；异参/异操作者拒绝。
- [x] 银行动态状态原子恢复固定种子，旧验证失效，故障回默认；失败回滚且只按原号重试。
- [x] 只读当前轮次重启可见；旧轮资金写入拒绝，新轮正常对照通过。
- [ ] 定向测试、独立 Standards/Spec 审查与 PR 回交；不代签 PM、安全或整体 E2E 接受。

验证与边界：[实际运行记录](../verification.md)。
