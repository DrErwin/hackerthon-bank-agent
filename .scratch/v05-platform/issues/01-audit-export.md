# 01：管理端审计导出 F35 与 F24 audit 下载分支

Ticket ID: v05-platform/01
Type: 开发
Owner: Erwin
Status: in_progress（2026-10-21 领取，同日交付）
Directory: `backend/app/api/` + `backend/app/audit/` —— **PM 2026-10-21 授权一次交付**：整轮导出要在审计只读端补一个可选的筛选范围，端点与下载分支在 api；两者同属底座（Erwin），按一次交付、一个 PR 落地，跨两个底座目录在票面如实留痕，不再拆成两票两 PR。
Package: [v04-platform/packages/01：v0.4 底座、Agent 与模拟银行](../../v04-platform/packages/01-foundation-agent-mockbank.md)（#121 原登记为该包范围外的遗留，按 PM 决定提前实施）
Spec: [v05-platform 场景规格](../spec.md)
Core scenarios: 契约 §6.7 F24（audit 分支）、§6.8 F35；继承 [v04-platform P04](../../v04-platform/spec.md) 的「导出范围由后端固定、下载受控、内容脱敏」口径
Verification: E2E 在 `backend/app/api/test_app.py`（HTTP 边界 + 真实运行时 + 真实审计库）：A01 整轮导出与冻结包 / A02 任务范围 / A03 权限与范围拒绝 + 审计下载不绑会话 / A04 冻结与同 request_id 幂等 / A05 脱敏与只读（不调用模型、不触达银行）。证据见 Comments。
Blocked by: None
Source issue: [Issue #121](https://github.com/DrErwin/hackerthon-bank-agent/issues/121)

## 交付

1. F35 `POST /api/v1/admin/audit/exports`：`request_id`、`demo_round_id`、`task_id?` → `ExportView(kind=audit)`；创建即生成并冻结 JSON 证据包（`status=ready`），缺省 `task_id` 为整轮范围。
2. F24 `GET /api/v1/exports/{export_id}/download` audit 分支：复核独立管理身份 + 创建时固定范围，未就绪 409；不绑定创建时会话、不重走验证。
3. 审计留痕：导出与下载各写 `audit.accessed`（`action=export|download`、`export_id`、`permitted`）。
4. 存储：导出资源表允许 audit 导出无报告 / 无会话线程（旧演示库做一次保留数据的结构迁移）。
5. 只读端：`AuditReader.export_json` 支持可选任务范围（不传即整轮），`audit.accessed` 携带 `export_id`。

## 边界与依赖

- 不改公共契约（F24/F35 与 `ExportView` 均已定义），不改安全策略、不触达银行规则；审计数据源只用既有只读端。
- 不在本票：前端管理页入口（PM 决定本次不加，已登记为已知限制）、F25—F32、安全评测覆盖登记（安全线）。
- 审查与验证：AI 双轴审查（规范 / 票面）+ CI，非真人审查；真人安全签核不在本票范围。

## Comments

- 2026-10-21 22:40：PM Erwin 指派「把 121 做了」，确认两条口径——①跨 `api/` + `audit/` 两个底座目录一次交付、一个 PR（票面留痕）；②本次不加前端管理页入口，只交后端契约能力，并注明该限制。建票开工。
