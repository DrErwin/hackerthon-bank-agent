# 09：报告与导出链路的秘密泄漏扫描证据（交付包验收标准 2 补证）

Ticket ID: v04-platform/09
Type: 测试 / 证据
Owner: Erwin
Directory: backend/app/api/
Status: resolved（[PR #130](https://github.com/DrErwin/hackerthon-bank-agent/pull/130) squash `e46522a` 合入 main，2026-10-14；Standards 轴无 P0/P1、Spec 轴无 P0，P1/P2/P3 全部处置〔AI 审查、非真人，意见与处置见 PR 评论〕；证据：新用例 1 passed、api 76 passed、后端全量 536 passed + 模拟银行 14 passed、CI 绿；生产代码零改动）
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
- **验收标准 2 的证据归属**（Spec 轴审查 P2 要求写明）：本票只补"无验证码或秘密泄漏"这一子项；其余子项由既有用例覆盖、本票不重复——本人范围校验（`test_app.py` 报告 owner / 管理员 404、导出越权 404）、未过验证不给内容（明细下载 409）、下载路径受控（路径校验与未就绪 409/404）。本票**不改变** P04 行「已验（平台链路级）」的判词。

## Comments

- 2026-10-14 Erwin（AI 代填）：按交付包验收标准 2 建立本票。发现路径：票 05 前置准备完成后复核平台线验收证据，发现 v0.3 已有的验证码存储扫描（`stored_code_leak`）从未覆盖 v0.4 新增的导出链路，而三张被漏掉的表正是该链路写的。
- 2026-10-14 交付 1—3 落地（[PR #130](https://github.com/DrErwin/hackerthon-bank-agent/pull/130)）：`test_export_secrets.py` 跑完整条明细导出链路后扫描全部对外产物（含验证历史回放）与平台库全部用户表（按 `sqlite_master` 枚举，新表自动纳入），并对 `api_exports` / `api_reports` / `api_tasks` 加**最小行数断言**避免在空表上静默通过；演示码响应断言 `no-store`。证据：新用例 1 passed、api 全目录 76 passed、后端全量 536 passed、模拟银行 14 passed、CI 绿。
- 2026-10-14 **交付 4 落地**（纯文档提交）：交付包「验收证据索引」P03/P04 行已回填本票（含扫描口径、两张被漏掉的表与注入检验），并写明验收标准 2 其余子项的归属。
- 2026-10-14 注入检验（证明扫描两半各自咬得住）：①库侧——把 `store.receipt()` 的 HMAC 摘要改成明文请求体 → 用例报出 `api_requests` 的具体行；②响应侧——让验证响应回显验证码 → 用例报出 `verify`。两次注入均已还原，生产代码零改动。
