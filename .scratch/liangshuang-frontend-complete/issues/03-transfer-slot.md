# 03：完整转账业务插槽

Ticket ID: liangshuang-frontend-complete/03
Type: 开发
Owner: 梁爽
Directory: frontend/
Status: planned
Package: [frontend-complete/packages/01：v0.4 完整前端实现与替换](../../frontend-complete/packages/01-v04-complete-frontend.md)
Spec: [梁爽完整前端实施规格](../spec.md)
Core scenarios: [FE-01、FE-03、FE-04](../../frontend-complete/spec.md)
Blocked by: [liangshuang-frontend-complete/02](02-frontend-shell.md)
Verification: 先以契约 demo 走通候选→确认→验证→等待→结果及恢复 / 异常；真实接口可用后重跑同一路径，结果事实与交易号只认后端返回。

## 交付与验收

- 接真实数据源前，先运行前端公共类型生成，确认导出 `TaskRecordsView` 及最新公共字段，不手写平行类型。
- 接真实 `ShellDataSource` 时，用 F39 `GET /tasks/{task_id}/records` 重建确认 / 验证历史，替换本地缓存编号再经 F14 / F16 查回的变通；验证清缓存 / 跨会话恢复、只读展示及任务所有权拒绝路径。
- 按已确认原型实现转账候选、修改、确认、验证、执行、结果及异常状态。
- 保留历史确认 / 验证记录，防止旧确认、过期操作和重复点击造成再次提交。
- 费用、银行、交易号及最终状态仅展示接口返回；缺字段走公共变更流程。
- 邀请 Ringo 审查确认 / 验证交互，联调结果交 Erwin 验收。

## Comments

- 2026-10-13：承接 [PR #108 返修清单](https://github.com/DrErwin/hackerthon-bank-agent/pull/108#issuecomment-6126114071)。F39 后端已由 PR #109 / #110 / #112 / #111 合入；本票落实类型生成与真实回放接入，不在票 02 的 stub 中提前实现。
- 票 02 的 Ringo 审查为 PM 豁免，不延伸至本票或票 05。接入前核对 Issue #85 的可见性和保留口径复核情况，并请 Ringo 审查真实确认 / 验证和回放边界。
