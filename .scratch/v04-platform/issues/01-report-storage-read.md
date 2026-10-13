# 01：受控报告存储与 F21 读取

Ticket ID: v04-platform/01
Type: 开发
Owner: Erwin
Directory: backend/app/api/
Status: pr_open（[PR #115](https://github.com/DrErwin/hackerthon-bank-agent/pull/115) 待统一审查，2026-10-13 开出）
Package: [v04-platform/packages/01-foundation-agent-mockbank：v0.4 底座、Agent 与模拟银行](../packages/01-foundation-agent-mockbank.md)
Spec: [v04-platform 场景规格](../spec.md)
Core scenarios: [P03 报告读取](../spec.md)（转账链路不回退的回归断言随本票 E2E 一并覆盖）
Verification: `backend/` 下运行本票新增与既有 api 测试（命令与输出记入本票 Comments）。E2E：seed 受控报告后 F21 本人可读、越权拒绝、卡片字段与契约 §5.3 一致且不含原始全量明细。局部验收 = F21 读写路径；整条路径（真实账单报告 → F21）由票 04 接线与联合验收覆盖，不把局部通过标为 P03 场景通过。
Blocked by: None（`BillReport` 契约模型已在 main，PR #113）
Source issue: [Issue #87](https://github.com/DrErwin/hackerthon-bank-agent/issues/87)

## 交付

1. 受控报告存储：模块结果中的 `BillReport`（§5.3）落库，保存 `report_id` 与归属（用户 / 会话 / 任务），沿用 `api/store.py` 的 ApiStore 既有模式，不建第二套持久化体系。
2. F21 `GET /reports/{report_id}`：返回 §5 BillReport 页面卡片内容；校验本人范围；不含原始全量明细、趋势或异常标记（卡片只含本期 1 / 2 / 3 内容块）。
3. E2E 测试：本人读取、越权拒绝、卡片内容边界；既有转账链路回归无新增失败。

## 边界与依赖

- 不在本票：导出链路（票 02）、`report_ready` 事件发射（票 04；本票只保证报告可落库可读）、F24 audit 分支与 F35（归属待 PM 决定）。
- 若实现中发现需要 `backend/app/storage/` 公共存储层或 `backend/app/contracts/` 补字段：按一票一目录另开票（05 起），本票不跨目录。

## Comments

- 2026-10-13：双轴审核通过后按 PM 指示建立（审核记录见交付包 Comments）。
- 2026-10-13 实施（分支 `v04-platform-01-report-storage`，先红后绿）：`store.py` 新表 `api_reports` + `save_report` 幂等；`service.py` `capture_report`（`link()` 归属校验）/ `report`（本人范围，越权与不存在一致 404）；`app.py` `GET /api/v1/reports/{report_id}`（no-store）；E2E 2 项（owner 读取 / 管理员 404 / 响应无 transactions 明细行 / capture 绑定本人任务）。验证：`app/api` 65 passed、后端全量 420 passed（本机）。[PR #115](https://github.com/DrErwin/hackerthon-bank-agent/pull/115) 待后续会话统一审查，不在实施会话自审自合。
