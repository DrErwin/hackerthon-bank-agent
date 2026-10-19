# 场景 05 订阅代扣评测集（v0.4 · 完整验收集）

票 [`v04-subscription/10`](../../.scratch/v04-subscription/issues/10-full-eval-coverage.md) 的**完整验收集**：在票 [`07`](../../.scratch/v04-subscription/issues/07-subscription-evals.md) 的 17 条主路径黄金用例上补齐到 **48 条**，逐条覆盖 PRD [`05-订阅代扣管理`](../../docs/prd/05-订阅代扣管理-PRD-2026-10-19.md) 的 T01–T17 与 E01–E12 的全部适用分支。逐条 8 字段见 [`cases.md`](cases.md)；机器可读期望的正本是 [`golden_cases.json`](golden_cases.json)，测试逐条断言，二者不得脱节。

> **运行前提**：基座须包含票 [`09`](../../.scratch/v04-subscription/issues/09-cancel-refusal-and-unknown-recovery.md)（PRD T05/E06/E09 的如实回执与待核实回查）与票 08 审计脱敏修复（`f202e5d`）。不含票 09 的提交上 `SUB-CAN-12/13/14/18/19` 会按预期变红。

- 运行层次：**平台运行时** —— 真实 `MockBankService`（B29/B30 与签约、流水种子）、真实 `SecurityGate` + `DeterministicExecutor`、真实 `AuditJournal`/存储、真实 `DemoSecurityPolicy`、模块自身 checkpoint 状态机。
- 唯一替身：**模型入口**（`harness.RoutedPlanner` 直接给出目标 capability）。本集不评模型理解力，真实 GLM 的意图路由另计。
- HTTP 层（F05/F06/F07/F08/F10）由票 06 的 `backend/app/api/test_subscription_api.py` 覆盖，本集不重复；前端渲染/语音播报、演示管理能力（B26/B27）不在本集。
- 用例按主题分三个文件，共用 `golden_cases.json` 与 `harness.py`，断言口径一致：
  - [`test_subscription_evals.py`](test_subscription_evals.py)：主路径、失败与恢复、三条红线、观测项（22 条）；
  - [`test_subscription_read_evals.py`](test_subscription_read_evals.py)：清单、提醒、数据不足、隔离与注入（12 条）；
  - [`test_subscription_cancel_evals.py`](test_subscription_cancel_evals.py)：消歧、验证边界、幂等、审计与脱敏（14 条）。

## 1. 怎样跑

```powershell
$env:PYTHONPATH = "<仓库副本>\backend"   # 可选：conftest.py 已把本检出的 backend 置前
$env:PYTHONIOENCODING = "utf-8"
cd <仓库副本>

# 全量评测（48 条）
python -m pytest evals/subscription -q

# 单条用例
python -m pytest evals/subscription -q -k sub_eval_15

# 后端全量回归（本票不改 backend/，用于确认没有连带影响）
python -m pytest backend -q

# 生成运行证据（写 evidence/<日期>/ 的原始报告 + manifest.json + manifest.md）
$env:SUB_EVAL_EVIDENCE = "evals/subscription/evidence/<日期>"
python -m pytest evals/subscription -q
```

`conftest.py` 与 `stability_sample.py` 都会把**本检出**的 `backend/` 插到 `sys.path` 最前，避免共享 venv 里 editable 安装的主仓库 `app` 抢先被导入；证据与稳定性取样都会写入 `app_file` 字段，用来核对「测的是哪棵树」。

## 2. 覆盖表

| 功能/规则及依据 | 正常 | 反例 | 边界 | 失败/恢复 | 交叉情况 | 缺口与依赖 |
|---|---|---|---|---|---|---|
| SOP-1 签约事实盘点与三种事实等级（T01；契约 §5.5） | SUB-INV-01、SUB-INV-05 | — | — | — | SUB-INV-09 | 真实模型对口语的理解另计 |
| SOP-1 无数据（T02） | SUB-INV-03 | — | — | — | — | — |
| SOP-1 签约读取失败不退化（T03） | — | — | — | SUB-INV-04 | SUB-INV-04（流水正常也不退化） | — |
| SOP-1 数据不足（T15/E12；契约 §5.9） | — | SUB-INV-02（0 个月） | SUB-INV-06（1 个月） | — | SUB-INV-02 | 用户说「最近 1 个月」的查询范围入参未接（平台入口不传参） |
| SOP-1 疑似识别与外部引导（T08/E02） | SUB-GUD-01、SUB-GUD-02 | SUB-GUD-02（不判定盗刷） | SUB-INV-01（共享流水多条命中） | — | SUB-RED-02 | E02「不是我订的」多轮分支需真实模型 |
| SOP-3 未来 30 天提醒（T14） | SUB-REM-01、SUB-INV-01 | — | SUB-REM-02（D+30/D+31） | — | SUB-REM-04 | — |
| SOP-3 无生效签约（SOP-3 例外） | — | SUB-REM-03 | — | — | — | — |
| SOP-3 下一期日期缺失不猜（SOP-3 例外） | — | SUB-REM-04 | — | SUB-CAN-17（退订侧同源） | SUB-REM-04 | 「需要核实」标注未实现（§8） |
| SOP-2 单笔退订全链路（T04） | SUB-CAN-01 | SUB-CAN-12、SUB-CAN-18 | SUB-CAN-17 | SUB-CAN-13、SUB-CAN-14、SUB-CAN-19 | SUB-RED-01 | — |
| 会话级基础验证复用（SF03；§5.1） | SUB-CAN-02 | — | — | SUB-CAN-09 | SUB-CAN-10 | 验证码重发/过期属 F19/F28 与银行层（票 06 + 安全评测） |
| 消歧与拒绝批量（E01/T12/E08） | SUB-CAN-03、SUB-CAN-05 | SUB-DIS-01 | SUB-CAN-04 | — | SUB-DIS-02 | — |
| 已退幂等（E04/T13） | SUB-IDM-01 | — | — | SUB-CAN-16 | SUB-RED-02 | 当期 `processing` 分支 v0.4 无该状态 |
| 反悔/取消（E05/T06） | — | SUB-IDM-02 | — | SUB-CAN-07 | SUB-CAN-10、SUB-CAN-11 | — |
| 验证失败终止与重试边界（E10） | — | SUB-VFY-01 | SUB-CAN-08（第 3/4 次） | SUB-CAN-09 | — | — |
| 验证强度边界：非 LOW 不降级（spec §5.3/§8.4） | — | SUB-VFY-03 | — | — | — | 策略当前对退订只给 LOW/HIGH；用例守住注入非 LOW 裁决时仍走动作级 step-up、不降级为会话验证码 |
| 高危阻断（T09；§5） | — | SUB-VFY-02 | — | — | SUB-RED-03 | 真实反诈检测效果属安全评测 |
| 防重复（T11/E07） | — | SUB-CAN-06 | — | SUB-CAN-06 | SUB-CAN-13 | 第二次点击的「已在处理/已退过」文案属 F06 幂等回执（API 层），本集只钉单次执行 |
| 关键内容变化/确认失效（§5.2） | — | SUB-CAN-11 | — | SUB-CAN-10 | SUB-CAN-10 | 平台在此分支有两种安全收尾（重出确认单 v2 / 安全拒绝），受进程哈希序影响；本集断言共同安全不变量，确定性另记缺口（§8） |
| 结果未知与 B14 回查（T05/E06） | SUB-CAN-13 | SUB-CAN-14 | — | SUB-CAN-13、SUB-CAN-14、SUB-CAN-19 | — | 多进程并发、跨演示轮次回查不在本集 |
| 商户名注入（T10；§5.5） | SUB-INV-08 | SUB-INV-08 | — | — | SUB-VFY-02 | 真实模型的注入抵抗属安全评测 |
| 跨用户（E11/T16；§5.4） | SUB-INV-07 | SUB-INV-07 | — | — | SUB-INV-07 | 拒绝话术属规划层（§8） |
| 话术红线（§2.3/§5.3；PRD §五） | SUB-RED-03 | SUB-RED-03 | — | SUB-RED-03 | SUB-RED-03 | 只覆盖后端可见文本，前端渲染与语音播报另计 |
| 确认门红线 | SUB-RED-01 | SUB-RED-01 | SUB-RED-01 | SUB-CAN-07 | SUB-CAN-13 | — |
| 审计链路（§5.10） | SUB-SEC-01、SUB-OBS-03 | — | — | — | — | 写前 AuthorizationSnapshot 只在 SENSITIVE 动作产生，而退订在 spec/契约声明为 MODIFY（见 §8）；审计规则验收归安全侧 |
| 脱敏与数据最小化（§5.6） | SUB-SEC-02、SUB-INV-09 | — | — | — | SUB-SEC-02 | — |
| 首启稳定性与终止任务重复读取（票 05/08 观测项） | SUB-OBS-01、SUB-OBS-02、SUB-OBS-03 | — | — | SUB-OBS-02 | — | 底座修复属票 08 PR |

> 数量口径：`evals/README.md` §四「每功能 ≥10 条、每类异常 ≥3 条」是完整验收集的规模下限；本集按「把当前阶段适用的规则和关键分支列全」补齐（PM 2026-10-19 拍板：不硬凑语义重复用例），逐类异常的实际条数与 Blocked 理由见 §3。

## 3. 异常类覆盖（E01–E12）

| 编号 | 条数 | 用例 | 备注 |
|---|---|---|---|
| E01 说不清/多候选 | 4 | SUB-CAN-03、SUB-CAN-04、SUB-CAN-05、SUB-DIS-01 | 含用文字而非选项 id 回答候选 |
| E02 只有流水、无签约 | 3 | SUB-GUD-01、SUB-GUD-02、SUB-RED-02 | 「不是我订的」多轮分支 **Blocked**（需真实模型） |
| E03 追问退已扣款 | 0 | — | **Blocked**：退款追问话术属规划/问答槽位，脚本替身入口无法断言 |
| E04 处理中/已退 | 2 | SUB-IDM-01、SUB-CAN-16 | `processing` 分支 v0.4 无该状态（契约 §7A）；「无 active 提醒」见 E12 行，「无下一期日期不硬退」见覆盖表 SOP-3 例外行（SUB-CAN-17） |
| E05 反悔/取消/会话失效 | 4 | SUB-IDM-02、SUB-CAN-07、SUB-CAN-10、SUB-CAN-11 | 覆盖确认前、验证阶段、换会话、内容变化四个时点 |
| E06 结果未知 | 3 | SUB-CAN-13、SUB-CAN-14、SUB-CAN-19 | 回查成功/未受理/银行判失败三种收尾 |
| E07 重复点击 | 2 | SUB-CAN-06、SUB-CAN-13 | 同一确认记录只执行一次 |
| E08 批量全退 | 3 | SUB-DIS-01、SUB-DIS-02、SUB-CAN-04 | 拒绝 + 退出 + 选一项后继续 |
| E09 银行明确拒绝 | 2 | SUB-CAN-12、SUB-CAN-18 | 另有银行层错误码用例见 `backend/app/services/test_subscriptions.py` |
| E10 验证失败/边界 | 3 | SUB-VFY-01、SUB-CAN-08、SUB-CAN-09 | 第 3 次终止、第 4 次拒绝、未满 3 次可恢复 |
| E11 跨用户 | 1 | SUB-INV-07 | 确定性隔离已断言；拒绝话术 **Blocked**（规划层） |
| E12 数据不足 | 3 | SUB-INV-02、SUB-INV-06、SUB-REM-04 | 0 个月/1 个月/日期缺失三种证据不足 |

## 4. 三条红线

1. **确认门红线**：`SUB-RED-01` 逐步核对「未确认 / 已确认未验证 / 验证码已通过但未绑定」三个阶段银行提交均为 0，只有绑定后才发生 1 次；`SUB-CAN-13/14/19` 断言待核实与回查阶段不重复提交（`cancel_operations` 恒为 1 或 0）；`SUB-DIS-01/02` 断言批量一键全退被拒且退出不产生提交。
2. **口径边界红线**：`SUB-RED-02` 断言疑似周期扣费与已解约项都不进确认门、不调 B30；`SUB-GUD-01/02` 断言外部渠道引导与「不判定盗刷」；`SUB-INV-02/06` 断言证据不足时不报「干净」。
3. **话术红线**：`SUB-RED-03` 对一轮内全部用户可见文本（消息、交互提示、选项标签、确认单字段）断言零禁用词（含同义表述），并断言确认单与回执只承诺「从下一期（…）起不再自动扣费，之前已经扣掉的钱不退」。

## 5. 稳定性观测（票 05 审查项）

票 05 审查报告过约 3/60 的偶发首启失败（`SecurityError` → `SUBSCRIPTION_INTERNAL_ERROR`）。本集用 [`stability_sample.py`](stability_sample.py) 在同一组装上连跑首启取样，定位到**底座审计脱敏缺陷**（票 08 `f202e5d`）：卡号掩码 `\d{12,19}` 会改写不透明引用 `sub-ref-<sha256[:24]>`，使审计证据键与事件引用不再一致。

| 观测 | 取样 | 结果 | 证据 |
|---|---|---|---|
| 修复前（`9741053`） | 150 次首启 | **16 次失败**（10.7%），全部 `SUBSCRIPTION_INTERNAL_ERROR`；门决策此前均为 `allow`，失败发生在审计写入 | [`evidence/2026-10-19/stability-pre-fix.json`](evidence/2026-10-19/stability-pre-fix.json) |
| 引用脱敏探针 | 20000 个 `sub-ref-<sha24>` | 修复前 **407 个被改写**（2.04%，如 `sub-ref-86e50149658661312a9e0b35 → sub-ref-86e****1312a9e0b35`）；修复后 **0** | [`evidence/2026-10-19/audit-ref-probe.json`](evidence/2026-10-19/audit-ref-probe.json) |
| 修复后（`f202e5d`） | 150 次首启 | **0 次失败**（150/150 `succeeded`） | [`evidence/2026-10-19/stability-post-fix.json`](evidence/2026-10-19/stability-post-fix.json) |

复跑观测：

```powershell
python evals/subscription/stability_sample.py --attempts 150 --label <标签> --out evals/subscription/evidence/<日期>/stability-<标签>.json
```

`SUB-OBS-01` 把同一性质钉进回归（每次评测跑 10 次首启，要求 0 次 `SUBSCRIPTION_INTERNAL_ERROR`）。底座修复属票 08 的 PR，本集不修改 `backend/`。

## 6. 证据

`evals/README.md` §六 的正本与索引都落在 [`evidence/<YYYY-MM-DD>/`](evidence/)：

- `subscription-platform-<UTC 时间戳>.json.gz`：本次运行的原始结构化报告（逐用例状态、逐条断言名与通过情况、失败清单、命令、解释器、`app_file`）；文件名唯一，不覆盖。
- `manifest.json`：台账（标签、层、**受测提交 SHA**、`dirty_paths`、命令、状态分布、断言统计、报告解压后 sha256）；`dirty_paths` 必须为空，否则说明证据不是在某个提交上跑出来的。
- `manifest.md`：人读摘要（以上字段 + 本次运行逐用例表）。

生成方式见 §1 的 `SUB_EVAL_EVIDENCE`；未设置该环境变量时评测不写任何文件。

## 7. 替身与真实链路分界

| 组件 | 本评测集里的形态 |
|---|---|
| 模型入口 | **替身**：`RoutedPlanner` 直接返回目标 capability（真实 GLM 路由不在本集） |
| 模拟银行 | 真实 `MockBankService`：B29/B30、B14、`bank_operations` 幂等、签约与流水种子（含共享账单流水）；用例注入的失败/超时属前置状态，不修改银行规则 |
| 安全门与执行器 | 真实 `SecurityGate` + `DeterministicExecutor` + `ConfirmationService`/`SQLiteSecurityState` |
| 风险裁决 | 真实 `DemoSecurityPolicy`（含 `subscription.bank.cancel_subscription` 的 LOW/HIGH 分支与 fail-closed 证据） |
| 业务模块 | 真实 `SubscriptionEntry` 状态机与 checkpointer；单测里的 `FakeGate`/`FakeBank` 均未使用 |
| 审计与存储 | 真实 `AuditJournal`、`ApplicationStore`、`tool_operations`/`security_executions` |
| 时间 | 固定银行时钟 `2026-10-19 04:00Z`（北京 12:00），种子偏移与提醒窗口因此确定 |
| 故障注入 | `harness` 用例注入属**前置状态**，不改银行规则与安全策略：`arm_cancel_timeout` 基于共享 `BankGateway` 的私有写超时预算（`_transfer_timeout_seconds`）+ 对 `MockBankService.cancel_subscription` 的延时包装，模拟「网关等待超时、银行后台仍在处理」；`fail_cancel_with` / `fail_mandates_query` 让银行返回指定错误码；`fake_failed_operation` 让 B14 回查返回银行判失败。均为同步替身，不 sleep 真实业务时长（仅短延时以越过注入的超时预算） |

## 8. 未覆盖与 Blocked（如实）

| 条目 | 原因 | 提供方 |
|---|---|---|
| T17 演示重置 / 时间快进（B26/B27） | 后端未实现这两个演示管理能力，无法在评测里伪造重置与快进 | 演示管理能力（另开票） |
| E03 / T07 退款追问话术 | 「已扣的不退、只停下一期」属规划/问答槽位，脚本替身入口无法断言 | 平台规划层 |
| E11 / T16 拒绝话术 | 「只能查和退本人」属规划层；确定性隔离已由 `SUB-INV-07` 覆盖 | 平台规划层 |
| E02 第二分支「不是我订的」→ 疑似盗刷引导 | 需多轮模型交互 | 平台规划层 |
| E04 当期 `processing` 分支 | v0.4 契约无该状态（§7A） | 契约/银行后续版本 |
| `reminder_days` / `status_filter` 参数化 | 平台入口（S01 逻辑入参）未接线，评测无法从用户请求传入 | 平台规划槽位 |
| SOP-3「下一期异常需核实」标注 | 只实现「不猜日期」，标注文案未实现；`SUB-REM-04` 断言不猜半边 | 订阅模块后续 |
| 关键内容变化后的平台确定性 | 同一用例（`SUB-CAN-11`）在 `PYTHONHASHSEED` 不同时收尾不同：一支把同一确认单重新冻结为 v2（`waiting_approval:confirmation`），一支 `failed`/`SECURITY_REJECTED`（上游 `OPERATION_CONFLICT`）；两支都零提交、协议 `active`。评测改为断言两支共同的安全不变量，非确定性本身属平台实现问题（待开修复票） | 平台 / 订阅模块后续 |
| 退订的写前 AuthorizationSnapshot | 取消订阅在 spec/契约中声明为 `OperationLevel.MODIFY`（二级），安全门只在 `SENSITIVE` 动作前写授权快照；PRD §5.10 称其为三级敏感操作，两处口径不一致。`SUB-SEC-01` 只断言审计链路与操作编号，不伪造快照断言 | 安全侧 / 契约口径（Ringo 与 Erwin 确认后再定） |
| 真实 GLM 意图理解、前端渲染/语音播报、两进程并发同一退订 | 属真实模型 / 前端 / 并发评测 | v0.5 端到端 E2E 与安全评测 |
