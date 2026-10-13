# 09：报告与导出链路的秘密泄漏扫描证据（交付包验收标准 2 补证）

Ticket ID: v04-platform/09
Type: 测试 / 证据
Owner: Erwin
Directory: backend/app/api/
Status: in_progress
Package: [v04-platform/packages/01-foundation-agent-mockbank：v0.4 底座、Agent 与模拟银行](../packages/01-foundation-agent-mockbank.md)
Spec: [v04-platform 场景规格](../spec.md)
Core scenarios: [P03 报告读取、P04 卡片/明细导出](../spec.md)
Verification: 明细导出全链路跑完（创建 → F19 演示码 → 验证 → CSV 下载）后，对**所有对外产物**（创建 / 验证回执、导出状态、任务视图、F21 卡片、CSV、SSE 事件）与**平台库全部用户表**扫描验证码；CSV 保持银行侧打码与商户名口径；F19 演示码响应为 `no-store`。
Blocked by: 无
Source issue: 无（交付包验收标准 2「报告与导出无验证码或秘密泄漏」的证据补齐）

## 交付

1. 新增 `backend/app/api/test_export_secrets.py`：复用 `test_verification_fault.py` 的 `stored_code_leak`（token 边界匹配——6 位数字在时间戳、UUID、金额里频繁巧合出现，整行字符串比对会假报）；对外产物逐项扫描。
2. 平台持久层扫描**枚举全部用户表**（`sqlite_master` 而非硬编码名单）：既有扫描（`test_verification_fault.py:83-88`）只覆盖 `api_requests` / `api_events` / `tasks` / `audit_events` / `checkpoint_*`，**恰好漏掉导出链路写入的 `api_exports` / `api_reports` / `api_tasks`**；枚举写法对新表自动生效。
3. 断言 F19 演示码响应 `Cache-Control: no-store`（验证码唯一允许的对外通道是受控演示提示）。
4. 证据回填交付包「验收证据索引」P03/P04 行。

## 边界与依赖

- 只改 `backend/app/api/`（新增一个测试文件与验收证据），不改生产代码。
- 银行侧留存验证码是既定事实（银行要校验它），不在扫描范围；扫描对象是**平台库与对外产物**。
- 本票不声称业务结论正确性（归账单线 BF03/BF06），只证"敏感值不外泄"。

## Comments

- 2026-10-14 Erwin（AI 代填）：按交付包验收标准 2 建立本票。发现路径：票 05 前置准备完成后复核平台线验收证据，发现 v0.3 已有的验证码存储扫描（`stored_code_leak`）从未覆盖 v0.4 新增的导出链路，而三张被漏掉的表正是该链路写的。
