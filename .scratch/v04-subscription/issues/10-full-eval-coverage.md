# v04-subscription/10-full-eval-coverage: 场景 05 订阅代扣完整验收集（T01–T17 / E01–E12）

Ticket ID: `v04-subscription/10-full-eval-coverage`
Package: [`v04-subscription/01`：订阅代扣管理端到端闭环](../packages/01-subscription-e2e.md)
Spec: [`.scratch/v04-subscription/spec.md`](../spec.md)（§4 SF01–SF07、§5.7、§6）
Core scenarios: PRD [`05-订阅代扣管理`](../../../docs/prd/05-订阅代扣管理-PRD-2026-10-19.md) T01–T17、E01–E12、§四/§五；承接票 07 的首批代表性 17 条
Verification: `pytest evals/subscription -q` 全绿并在最终提交归档证据；`pytest backend -q` 不回归（Windows 两条 20ms 计时抖动属 Issue #166，单跑复核）
Owner: Erwin
Directory: `evals/subscription/`
Status: in_progress
Blocked by: [`v04-subscription/09`：退订失败/结果未知如实回执](09-cancel-refusal-and-unknown-recovery.md)（T05/E06、E09 的断言依赖该修复）
Source issue: 交接单 `handoff-subscription-evals-2026-10-19.md`（PM 原话：自己审查现状、自己判断补哪些）

---

## 1. 目标

把票 07 的 17 条「主路径黄金集」补齐为**完整验收集**：覆盖 PRD T01–T17 与 E01–E12 的全部适用分支，机读期望与断言一一对应，覆盖表如实标注能力缺口。验收上限口径按 [`evals/README.md`](../../../evals/README.md) §三/§四：先把当前阶段适用规则与关键分支列全，再逐条覆盖正常 / 反例 / 边界 / 失败恢复 / 交叉。

## 2. 交付物（缺一不可）

1. `golden_cases.json` 与测试代码**不脱节**：每条用例的期望（路由、状态序列、终态、交互、银行操作数、协议状态、必需/禁止文案、事实数值）都能被断言，禁止只写文档不写机读期望。
2. `README.md` 覆盖表按「正常 / 反例 / 边界 / 失败恢复 / 交叉 / 缺口与依赖」六列更新；未覆盖与 Blocked 如实保留。
3. **同提交运行证据**归档 `evals/subscription/evidence/<日期>/`：原始报告 gzip + `manifest.json` + `manifest.md`，写清被测提交、解释器、用例数、断言数、sha256、`dirty_paths`（必须为空）。
4. 一张只动 `evals/subscription/` 的 PR；正文写清新增用例、对应 T/E 编号、实测数字、仍未覆盖项与依赖。

## 3. 覆盖矩阵（2026-10-19 实测核对后确定）

- **清单 / 盘点（SOP-1）**：无数据（T02）、签约读失败不退化（T03）、三种事实等级与排序、指定范围数据不足（T15 变体）、跨用户隔离（E11 确定性半边）、商户名注入（T10）、只读零副作用与脱敏、有疑似无签约。
- **提醒（SOP-3）**：30 天窗口与合计（T14）、D+30/D+31 边界、无 `active` 如实说明、下一期日期缺失不猜日期。
- **退订（SOP-2）**：文字消歧与未命中回菜单（E01）、批量后文字消歧、连点两次确认（T11/E07）、验证阶段取消（E05）、验证码第 3/4 次边界（E10）、错两次后正确（恢复）、换会话重新确认、关键内容变化使原确认失效、银行明确拒绝（E09，票 09）、超时 → 待核实 → B14 回查（T05/E06，票 09）、提交幂等（operation 行数=1）、已解约幂等（E04/T13）。
- **红线与审计**：确认门红线、口径边界红线、话术红线、审计链路与写前授权快照、脱敏（无验证码原文、无未打码账号）。
- **数量口径（PM 2026-10-19 拍板）**：约 48 条；每功能 ≥10、异常类逐类标注实际条数与 Blocked 理由，不用语义重复用例凑数。

## 4. 如实标注的 Blocked（不在本票内伪造断言）

| 条目 | 原因 | 提供方 |
|---|---|---|
| T17 演示重置 / 时间快进 | B26/B27 未实现，后端无该能力 | 演示管理能力（另行开票） |
| E03 / T07 退款追问话术 | 属规划/问答槽位，脚本替身入口无法断言 | 平台规划层 |
| E11 / T16 拒绝话术 | 同上；确定性隔离已覆盖 | 平台规划层 |
| E02 第二分支「不是我订的」→ 疑似盗刷引导 | 需多轮模型交互 | 平台规划层 |
| E04 当期 `processing` 分支 | v0.4 契约无该状态 | 契约/银行后续版本 |
| `reminder_days` / `status_filter` 参数化 | 平台入口不向 S01 传参 | 平台规划槽位 |
| SOP-3「需要核实」标注 | 未实现（不猜日期半边已断言） | 订阅模块后续 |

## 5. 验收

- `pytest evals/subscription -q` 在最终提交全绿；`pytest backend -q` 无新增失败。
- 覆盖表逐行可定位到用例编号或 Blocked 说明；README / 票据 / 报告三处数字自洽。
- 证据绑定最终提交（`dirty_paths` 为空），不写超出 runner 能力的「整树校验」措辞。

## Comments

- 2026-10-19 交接单要求先自行核对现状再定缺口；实测确认 T05/E09 为真缺陷（票 09），T17/E03/E11 等为能力缺口，已列入 §4。
