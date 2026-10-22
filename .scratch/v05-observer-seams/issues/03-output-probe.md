# 03 输出侧观察最小探针

Ticket ID: v05-observer-seams/03
Package: 无独立交付包——v0.5 平台遗留收口（[spec](../spec.md)），来源 [Issue #216](https://github.com/DrErwin/hackerthon-bank-agent/issues/216)
Spec: [v05-observer-seams/spec.md](../spec.md)
Core scenarios: S4、S5
Type: 开发
Owner: Erwin（AI 代行实施与审查，非 Ringo 本人审查）
Directory: `backend/app/audit/`
Status: Done
Blocked by: None
Source issue: Issue #216

## 交付物

新模块 `backend/app/audit/output_guard.py`（只依赖标准库与现有 `journal.redact`，不改冻结契约）：

```python
@dataclass(frozen=True)
class OutputFinding:
    kind: Literal["credential", "full_account", "personal_name", "personal_phone"]

@dataclass(frozen=True)
class OutputProbe:
    findings: tuple[OutputFinding, ...]   # 去重后的类别序列
    text: str                             # 已脱敏文本

def probe_output(text: str) -> OutputProbe
def probe_secrets(text: str) -> tuple[bool, str]   # 只查认证秘密（导出用）
```

识别口径（最小、可解释，不追求全量分类器）：

| 类别 | 口径 |
|---|---|
| `credential` | 现有 `SECRET_LABEL` 形状（「验证码是 / 密码为 / otp: xxx」）以及 6 位纯数字且前后文出现「码 / code」的验证码形状 |
| `full_account` | 连续 12—19 位数字（未掩码卡号 / 账号） |
| `personal_name` | 「姓名/户名/收件人：张三」形式的未掩码中文姓名 |
| `personal_phone` | 11 位手机号（未掩码） |

脱敏复用 `journal.redact(..., free_text=True)`，确保与现有审计脱敏口径一致；命中类别去重且顺序稳定。对空文本返回空结果（不报错）。**探针不产生授权/拒绝决定，只报告命中与已脱敏文本。**

## 验收（E2E/可复现脚本，真实数据形状）

| 编号 | 场景 | 通过条件 |
|---|---|---|
| C01 | 验证码泄露 | 「验证码是 123456」→ 命中 `credential`，输出文本不含原文 |
| C02 | 完整账号 / 手机 / 姓名 | 命中对应类别且被掩码；金额、时间、商户、交易号不受影响 |
| C03 | 正常文本不误伤 | 常规回复（含金额「500.00」、交易号 UUID、掩码账号 `****0002`）零命中、原文不变 |
| C04 | 只查秘密 | `probe_secrets` 对个人数据不判定，只报认证秘密，供导出使用 |
| C05 | 审计口径一致 | 脱敏结果与 `journal.redact(free_text=True)` 对同一输入一致（可断言等值） |

## 备注

- 本票只提供探针；出口接线在票 04（`backend/app/api/`）。不改 `journal.py` 既有 `redact` 行为。
- 不新增审计事件类型；命中留痕由票 04 用既有 `chat.message` / `audit.accessed` 事件表达。

## Comments

- **2026-10-22 交付**：[PR #218](https://github.com/DrErwin/hackerthon-bank-agent/pull/218) squash `23f6d42` 已合入。`probe_output` / `probe_secrets` 四类命中 + 审计口径一致的脱敏文本；验证 C01-C05（探针结果写入真实 AuditJournal 后回放，脱敏逐字节一致）。已知边界：无分隔符 6 位码只报告不掩码（票 04/07 按命中拦截）；机器载荷误报由票 08 修复。审查：AI 代行，非 Ringo 本人审查。
