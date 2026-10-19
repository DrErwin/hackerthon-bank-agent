# v04-subscription/08-audit-opaque-ref-redaction: 审计脱敏不得改写不透明引用

Ticket ID: `v04-subscription/08-audit-opaque-ref-redaction`
Package: [`v04-subscription/01`：订阅代扣管理端到端闭环](../packages/01-subscription-e2e.md)
Spec: [`.scratch/v04-subscription/spec.md`](../spec.md)（§5.3 读/写适配、§5.5 平台编排）
Core scenarios: SF01–SF06（审计链路；本票为跨场景底座修复）
Verification: 本票局部——`pytest backend/app/audit -q`；整条路径由 `07-subscription-evals` 的重复首启稳定性用例覆盖
Owner: Erwin（底座 `backend/app/audit/`）
Directory: `backend/app/audit/`
Status: resolved
Blocked by: None
Source issue: 票 06 联调阻塞（见 Comments）

---

## 1. 目标（Why & What）

**缺陷**：审计日志的通用脱敏会把**不透明引用**当成卡号改写，导致审计证据与事件引用对不上，安全门把已放行的动作降级为 `PAUSE/AUDIT_UNAVAILABLE`，业务任务随机失败。

链路（票 06 联调实测）：

1. `modules/subscription/reads.py` 的参数引用是 `sub-ref-<sha256 前 24 位>`（含 24 位十六进制）；
2. `audit/journal.py` 的 `ACCOUNT = \d{12,19}` 把其中 12–19 位的数字串改写成 `****XXXX`（实测 `sub-ref-2b5a4d19634889502aae10d4` → `sub-ref-2b5a4d196****9502aae10d4`）；
3. `append_in_transaction` 用**脱敏后**的事件算 `evidence_refs(clean)`，与**未脱敏**的快照键比对 → `ValueError("snapshot is not referenced by the event")`；
4. `security/gate.py` 将 sink 异常降级为 `PAUSE/AUDIT_UNAVAILABLE` → 模块视为 `SECURITY_REJECTED` → 任务 `FAILED`（银行状态不变，fail-closed）。

**影响量化**：4000 个随机订阅引用中 76 个（**1.90%**）被改写；一个盘点/退订任务会记 3–5 条带引用的安全决策，因此演示中约每 10–20 次订阅请求整单失败一次。票 05 独立审查在探针里观测到约 3/60 的偶发首启失败，与本缺陷比例吻合；转账侧引用是完整 UUID（`OPAQUE_UUID.fullmatch` 提前返回）暂未命中，但同一类风险的写法仍在（任何带前缀/非 UUID 的引用都会踩）。

> **目录边界**：只允许修改 `backend/app/audit/` 下的文件。

---

## 2. 改动清单

### 2.1 `journal.py`
- 新增不透明引用字段识别：`REF_FIELD = re.compile(r"(?:^|_)refs?$")`，覆盖 `evidence_ref`、`arguments_ref`、`parameters_ref`、`display_ref`、`result_ref`、`receipt_ref`、`content_ref`、`request_ref`、`response_ref`、`before_ref`、`after_ref`、`source_refs`。
- `redact(..., *, opaque: bool = False)` 增加不透明语义：命中 `*_ref` / `*_refs` 字段时，值**逐字保留**（仍是字符串/列表本身），不再套用手机号/卡号/姓名/地址掩码；已知秘密（`known_secrets`）与 `SECRET_LABEL` 仍照常替换（引用里出现秘密属异常，安全优先）。
- 其余字段与自由文本的脱敏行为**一字不变**。

### 2.2 `test_journal.py` 增补
1. 引用形如 `sub-ref-2b5a4d19634889502aae10d4`（含 16 位数字串）的事件：脱敏后 `arguments_ref`/`parameters_ref`/`evidence_ref` **逐字不变**；
2. 同一事件附挂 `snapshots={ref: {...}}` 时 `append_in_transaction` **不再抛** `snapshot is not referenced by the event`，且 `audit_evidence` 行可回查；
3. 对照：`card_number`/`account_number`/自由文本里的 12–19 位数字串**仍被掩码**（防止修复把真正的卡号一起放过）；
4. `source_refs` 列表里的引用同样逐字保留；
5. 已知秘密出现在引用中时仍被替换（安全优先的边界）。

---

## 3. 验收与自检命令

```bash
pytest backend/app/audit -q
pytest backend -q          # 不破坏既有审计/安全/转账/订阅用例
```

---

## Comments

- 2026-10-19 由票 06（API 接线）联调发现并量化；票 05 独立审查的偶发首启失败（约 3/60）经比例核对判定为同一根因。
- 修复方案选择**根因修复**（审计侧不改写不透明引用），不采用「让订阅引用避开长数字串」的局部绕过：后者只降低概率，且转账侧同类写法仍在。
- 2026-10-19 实施 + 独立审查（`f202e5d`）：**通过**，无必修项。审查以隔离副本对照实测：真实生产引用 `sub-ref-3e7c93f5a4c7820109414689` 在旧实现下抛 `snapshot is not referenced by the event`，门级端到端表现为 `pause/AUDIT_UNAVAILABLE`（ALLOW 被降级）；20 万采样旧实现 4117 次改写（2.058%）、新实现 0；`opaque` 命中的 17 个字段名全部为不透明标识符且与 PII 字段集合交集为空；5/5 变异被杀；整包 699 passed。
- 审查建议的「opaque 值若整体是 12–19 位纯数字才掩码」**未采纳**（记录理由）：当前所有引用产出点均为 uuid4 或 sha256 派生，纯数字引用不可达；而该守卫一旦命中合法数字型引用就会造成新的引用不一致，重新引入本票要修的失败模式（KISS/避免投机防御）。若未来出现由外部数据构造的引用，再按票评估。
- 历史数据不迁移：修复只对后续写入生效，本地旧数据目录可能残留被改写的引用行（读取时表现为 `evidence_status: missing`）；演示轮次前重置数据目录即可，如需迁移另开票。
- 合入 main：**PR #153**（squash `cd7c91a`）。
