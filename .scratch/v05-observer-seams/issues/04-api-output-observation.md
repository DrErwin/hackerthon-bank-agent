# 04 输出观察接线：回复 / SSE / 导出 / 记忆查看

Ticket ID: v05-observer-seams/04
Package: 无独立交付包——v0.5 平台遗留收口（[spec](../spec.md)），来源 [Issue #216](https://github.com/DrErwin/hackerthon-bank-agent/issues/216)
Spec: [v05-observer-seams/spec.md](../spec.md)
Core scenarios: S4、S5
Type: 开发
Owner: Erwin（AI 代行实施与审查，非 Ringo 本人审查）
Directory: `backend/app/api/`
Status: Todo
Blocked by: [v05-observer-seams/03 输出侧观察最小探针](03-output-probe.md)；回复路径另依赖 [v05-observer-seams/02](02-api-untrusted-material.md)
Source issue: Issue #216

## 交付物

1. **助手回复（含 SSE）**：在 `ApiService.message_view` 的 assistant 分支（任务回复、聊天回复、验证/导出结果消息都经过它）调用 `probe_output`：
   - 出现 `credential`：整条回复替换为固定安全文案（命中拦截），不展示原文；
   - 只有其它个人数据类别：就地脱敏后发布；
   - 命中时写一条 `chat.message` 审计事件：`role=assistant`、`outcome=denied`、`reason_code=OUTPUT_PROBE_BLOCKED`（脱敏类用 `OUTPUT_PROBE_REDACTED`）、证据为 `{"findings": [...], "action": "blocked|redacted"}`（不含原文）。SSE 因复用存储后的消息视图而同样干净。
2. **任务结果里的消息文本**：`publish_task` / `publish_message_job_task` 发布的 assistant 消息同样走上一条路径；任务 `message` 字段原文不落 API 消息表（探针在消息视图处生效即可）。
3. **导出下载**：`export_file` 返回前用 `probe_secrets` 检查文件内容（card HTML、details CSV、audit JSON）；命中认证秘密→ 不返回文件，记 `audit.accessed(action="download", permitted=false, reason_code="OUTPUT_PROBE_BLOCKED")`（沿用 `record_audit_download` 的签发方式），返回 503 `DEPENDENCY_UNAVAILABLE`（既有错误码，不新增契约枚举）；未命中照常下载。
4. **记忆查看出口**：F37 返回内容前用 `probe_output` 就地脱敏（记忆词表已挡秘密，这里是纵深防御；不改 `memory/` 目录）。
5. 不改 `backend/app/security/`；不新增审计事件类型。命中/脱敏均在 `evidence` 里可回放，原始秘密不落盘。

## 验收（HTTP E2E）

| 编号 | 场景 | 通过条件 |
|---|---|---|
| D01 | 回复拦截 | 替身规划器返回含「验证码是 123456」的 `ReplyOnly`；消息与 SSE 中都不含 `123456`，展示为固定安全文案；审计有 denied `chat.message` |
| D02 | 回复脱敏 | 回复含未脱敏完整账号 / 手机号；消息中为掩码，金额与业务事实不变；审计有 redacted 事件 |
| D03 | 干净回复 | 正常回复零命中，原文不变（不误伤金额、交易号、掩码账号） |
| D04 | 导出拦截 | 构造含认证秘密的导出内容（测试替身注入）；下载 503 且记 permitted=false 的 `audit.accessed`；正常导出照常 200 |
| D05 | 记忆出口 | F37 返回的记忆内容经过探针且不丢字段；词表内容与删除/墓碑行为不受影响 |

## 备注

- 导出探针只查认证秘密，不把「他人账单数据」当作泄漏（账单明细本来就是导出内容）；个人数据脱敏仍由导出生成器与审计 `redact` 负责。
- 命中留痕不得包含原文；证据只放类别与处置。
