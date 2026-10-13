# 02：导出链路（F22 卡片/明细导出 + F23 状态 + F24 受控下载）

Ticket ID: v04-platform/02
Type: 开发
Owner: Erwin
Directory: backend/app/api/
Status: blocked
Package: [v04-platform/packages/01-foundation-agent-mockbank：v0.4 底座、Agent 与模拟银行](../packages/01-foundation-agent-mockbank.md)
Spec: [v04-platform 场景规格](../spec.md)
Core scenarios: [P04 卡片导出与明细导出](../spec.md)
Verification: E2E 四态：明细导出验证成功 / 失败 / 过期 / 越权分别给出正确结果，未过验证不给内容；卡片导出无需再验证。下载：card 越权拒绝、details 非本人 / 非当前会话 / 非本次验证授权拒绝、未就绪 409；无验证码或秘密泄漏；下载路径为应用内受控相对路径。敏感导出暂停 / 恢复沿同一平台任务。命令与输出记入本票 Comments；P04 场景通过以本票 E2E + 前端联调证据为准。
Blocked by: [v04-platform/01：受控报告存储与 F21 读取](01-report-storage-read.md)
Source issue: [Issue #87](https://github.com/DrErwin/hackerthon-bank-agent/issues/87)

## 交付

1. F22 `POST /reports/{report_id}/exports`（request_id、kind:card|details）：card 为普通卡片导出；details 创建或找回敏感导出任务，**必须重新完成本次所需验证**后才生成文件，`ExportView.task_id` 必填（§6.7）。
2. F23 `GET /exports/{export_id}`：准备 / 等待验证 / 完成 / 失败状态查询，不重复生成。
3. F24 `GET /exports/{export_id}/download`：文件响应；card 核验本人报告范围，details 核验本人、当前会话及本次导出验证授权；未就绪 409；文件编号或链接本身不授权。
4. 文件格式与脱敏：card 首版导出 HTML 卡片、details 导出 CSV；内容按契约 §4.5 脱敏，HTML 转义与 CSV 单元格安全由导出器负责。
5. 口径：details 的原始统计范围由后端按 report_id 找回，不接受前端扩大账户或日期；会话变化后旧导出授权失效，需重走验证并关联当前会话；已生成文件也不能绕过下载时访问检查。

## 边界与依赖

- 跨线依赖（安全侧）：明细「再次验证」**复用 `backend/app/security/` 既有验证机制与 F16—F20 口径**，本票不改 Ringo 目录；PR 开出后请 Ringo 审查，如需新规则由安全线在 v04-security 登记（2026-10-13 审核意见：避免重演「缺口另登记给对应 owner、无人执行」）。
- 不在本票：F24 的 audit 分支与 F35 管理端审计导出（归属待 PM 决定）；报告内容正确性（账单线，周恩宇）。

## Comments

- 2026-10-13：双轴审核通过后建立；安全侧依赖按上述口径登记，通知方式待 PM 决定。
