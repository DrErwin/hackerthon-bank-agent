# 场景 05 订阅代扣评测集（v0.4）

票 [`v04-subscription/07-subscription-evals`](../../.scratch/v04-subscription/issues/07-subscription-evals.md) 的黄金评测集：把 spec §4 的 SF01–SF07 与三条红线（确认门 / 口径边界 / 话术）变成可复跑的机器断言，覆盖 PRD 验收例 T01/T04/T08/T09/T12/T13/T14/T15。

- 运行层次：**平台运行时** —— 真实 `MockBankService`（B29/B30 与签约、流水种子）、真实 `SecurityGate` + `DeterministicExecutor`、真实 `AuditJournal`/存储、真实 `DemoSecurityPolicy`、模块自身 checkpoint 状态机。
- 唯一替身：**模型入口**（`harness.RoutedPlanner` 直接给出目标 capability）。本票不评模型理解力，真实 GLM 的意图路由另计。
- HTTP 层（F05/F06/F07/F10）由票 06 的 API 测试覆盖，本票不重复。

## 1. 怎样跑

```powershell
$env:PYTHONPATH = "D:\hb-worktrees\sub-evals\backend"   # 或先 cd <worktree>\backend
$env:PYTHONIOENCODING = "utf-8"
cd D:\hb-worktrees\sub-evals

# 全量评测（17 个黄金用例）
python -m pytest evals/subscription -q

# 单条用例
python -m pytest evals/subscription -q -k sub_can_01

# 后端全量回归（本票不改 backend/，用于确认没有连带影响）
python -m pytest backend -q

# 生成运行证据（写 evidence/<日期>/ 的原始报告 + manifest.json + manifest.md）
$env:SUB_EVAL_EVIDENCE = "evals/subscription/evidence/2026-10-19"
python -m pytest evals/subscription -q
```

`conftest.py` 会把本 worktree 的 `backend/` 插到 `sys.path` 最前，避免共享 venv 里 editable 安装的主仓库 `app` 抢先被导入（证据里的 `app_file` 字段会打印实际被测包路径）。

## 2. 覆盖表

| 功能/规则及依据 | 正常 | 反例 | 边界 | 失败/恢复 | 交叉情况 | 缺口与依赖 |
|---|---|---|---|---|---|---|
| SOP-1 代扣盘点与三种事实等级（spec §2、§4 SF01；契约 §5.5/§5.9） | SUB-INV-01 | SUB-INV-02 | SUB-INV-01 | — | SUB-INV-01（已退项不混入待退/疑似） | 真实模型对口语的理解另计 |
| SOP-3 30 天提醒与 7 天标注（spec §2.2、§4 SF01） | SUB-INV-01 | — | SUB-INV-01（D+5/D+12 窗口与合计） | — | — | `reminder_days` 非 30 的参数化未覆盖 |
| SOP-2 单笔退订主链路（spec §4 SF02；契约 §5.5 `per_action`） | SUB-CAN-01 | SUB-RED-01 | SUB-VFY-03 | SUB-VFY-01 | SUB-CAN-02 | 银行侧失败码（`STATE_CONFLICT`/`ACCOUNT_UNAVAILABLE`）属模块/银行用例 |
| 会话级基础身份验证（确认验证字段：`basic_identity` + `scope=session`） | SUB-CAN-01 | SUB-RED-01 | — | SUB-VFY-01 | SUB-CAN-02 | 验证码过期/重发未覆盖（属票 03/06 用例） |
| 疑似周期扣费口径与外部引导（契约 §5.9 第 4/5 条；spec §4 SF04） | SUB-GUD-01 | SUB-INV-02 | SUB-INV-01（共享流水多条命中） | — | SUB-RED-02 | 收窄/误报口径由契约冻结，本票只断言行为不锁条数 |
| 消歧与拒绝批量（spec §2.3、§4 SF05） | SUB-DIS-01 | SUB-DIS-01（批量被拒） | — | — | — | 用文字（非选项 id）消歧未覆盖 |
| 已解约幂等（spec §4 SF06a） | SUB-IDM-01 | — | — | — | SUB-RED-02 | — |
| 确认前取消（spec §4 SF06b） | SUB-IDM-02 | — | — | — | — | — |
| 高危阻断（spec §4 SF06d；`demo_policy` 高危信号） | SUB-VFY-02 | SUB-VFY-02 | — | SUB-OBS-02 | SUB-RED-03 | 真实反诈检测效果属安全评测 |
| 验证失败终止（spec §4 SF06c，连续 3 次） | — | SUB-VFY-01 | SUB-VFY-01 | SUB-VFY-01 | — | 第 3 次与第 4 次之间的重试边界未覆盖 |
| 话术红线（spec §2.3/§5.3；PRD §五） | SUB-RED-03 | SUB-RED-03 | — | SUB-RED-03 | SUB-RED-03 | 只覆盖后端可见文本，前端渲染与语音播报另计 |
| 证据不足如实说明（spec §4 SF07；PRD T15/E12） | SUB-INV-02 | SUB-INV-02 | SUB-INV-02 | — | — | — |
| 首启稳定性 / 审计证据键（票 05 审查观测项；票 08 `f202e5d`） | SUB-OBS-01 | SUB-OBS-01 | — | `stability_sample.py` 两段观测 | — | 底座修复属票 08 PR，本票只留观测证据 |
| 审计模块标签（票 05 审查建议 1；审计契约 `event.module`） | SUB-OBS-03 | — | — | — | — | 只核对 `confirmation.changed`/`verification.changed`/`tool.*`/`security.decided` 四类 |
| 终止任务重复读取（票 05 审查建议；契约 §6.5） | SUB-OBS-02 | — | — | SUB-OBS-02 | — | — |

> 数量口径：本票按票据要求交付 SF01–SF07、三条红线专测与审查驱动补充用例（17 条自动化用例，逐条断言）。`evals/README.md` §四「每功能 ≥10 条、每类异常 ≥3 条」是**完整验收集**的规模目标，本轮范围见上表「缺口」列，未宣称完整覆盖。

## 3. 用例清单（8 字段模板）

字段与 [评测集编写指南](../README.md) §二一致：编号 / 业务维度 / 映射依据 / 前置环境与数据状态 / 用户指令·输入 / Agent 预期交互 / 预期结果与硬性断言 / 自动化映射 & 状态。逐条期望的机器可读版本在 [`golden_cases.json`](golden_cases.json)（含 `capability`、`state_sequence`、`final_status`、`interaction`、`bank_operations`、`mandates`、`requires_confirmation`、`verification`、`required_text`、`forbidden_text`、`facts`），测试逐条断言，二者不得脱节。

| 编号 | 业务维度 | 映射依据 | 前置环境与数据状态 | 用户指令/输入 | Agent 预期交互 | 预期结果与硬性断言 | 自动化映射 & 状态 |
|---|---|---|---|---|---|---|---|
| SUB-INV-01 | 盘点与提醒 | spec §4 SF01；PRD T01/T14 | 签约 sub_001 优酷 2500 月 active(D+5)、sub_002 云端网盘 3900 月 active(D+12)、sub_003 喜马拉雅 cancelled；共享流水含绿洲健身 3900×5 | 帮我查查有哪些自动扣费 | 直接返回清单与提醒，不进确认门 | `active_count==2`；`upcoming_renewals==2`；`upcoming_total_fen==6400`；优酷 `billed_count==6`/`billed_total_fen==15000`；回复含「7 天内会扣款」与 30 天提醒；绿洲健身在疑似区且 `can_cancel_in_bank==False`；**疑似总条数不锁死**（共享流水命中物业/水费/通信等属正确行为）；已解约项不混入待退与疑似 | `test_sub_inv_01_inventory_and_reminder` Passed |
| SUB-INV-02 | 证据不足 | spec §4 SF07；PRD T15/E12 | 同一银行只有签约种子、无任何流水（覆盖 0 个月） | 帮我查查有哪些自动扣费 | 如实说明证据不足，签约照常展示 | `suspected_scan_status=="insufficient_data"`；疑似区为空；回复含「账单记录不足 3 个月」；**严禁**「没有查到自动扣费/未发现异常」 | `test_sub_inv_02_insufficient_data_is_not_reported_as_clean` Passed |
| SUB-CAN-01 | 单笔退订全链路 | spec §4 SF02；PRD T04 | sub_001 下一期 D+5；已登录会话 | 把优酷视频自动扣费退了 | 确认单 → 短信验证码 → 回执 | 状态序列 `WAITING_CONFIRMATION→WAITING_VERIFICATION→succeeded`；验证 `purpose=="basic_identity"`、`scope=="session"`、`required_methods==["code"]`、无摘要、**非 mock_face**；确认单 6 项字段含「从下一期（2026-10-24）起不再自动扣费，之前已经扣掉的钱不退」；回执 `mandate_id=="sub_001"`、`effective_stop_at==previous_next_billing_at`；B29 复查已 cancelled；重复 resume 不产生第二笔操作 | `test_sub_can_01_single_cancel_full_chain` Passed |
| SUB-CAN-02 | 同会话复用验证 | spec §4 SF03 | 同一会话 S1，第一笔（sub_001）已通过会话级验证 | 再把云端网盘自动续费退了 | 仍出确认单，确认后直接成功 | 第二笔仍过 `per_action` 确认门；**不再要求新验证码**（挑战数 0）；状态序列 `WAITING_CONFIRMATION→succeeded`；银行操作总数 2 | `test_sub_can_02_second_cancel_reuses_the_session_verification` Passed |
| SUB-GUD-01 | 疑似项外部引导 | spec §4 SF04；PRD T08 | 绿洲健身 3900×5 快捷支付、无签约记录 | 帮我把绿洲健身的每月扣款退订 | 不进确认门，直接给外部关闭引导 | `WAITING_CONFIRMATION` 数为 0；银行操作 0；`can_cancel_in_bank==False`；回复含「银行那边没有…签约代扣记录」与「微信支付/支付宝」 | `test_sub_gud_01_suspected_clue_is_guided_outside` Passed |
| SUB-DIS-01 | 消歧与拒绝批量 | spec §4 SF05；PRD T12 | 两个可在线退订的 active 签约 | 把所有自动扣费都关了（spec 原话） | `WAITING_INPUT` 单选候选，拒绝一键全退 | 候选仅 `sub_001`/`sub_002`；拒绝文案含「每次只能退订一项」；选择前确认单 0、银行操作 0；选择 sub_001 后进确认门 | `test_sub_dis_01_batch_refused_then_one_choice_confirms` Passed |
| SUB-IDM-01 | 已退幂等 | spec §4 SF06a；PRD T13 | sub_003 已 cancelled | 把喜马拉雅自动续费退了 | 直接告知已退订 | 不改银行状态；确认单 0；回复含「此前已经退订」「无需重复操作」 | `test_sub_idm_01_already_cancelled_is_idempotent` Passed |
| SUB-IDM-02 | 确认前取消 | spec §4 SF06b | sub_001 已出确认单，用户点取消 | 把优酷视频自动扣费退了 → 取消 | 任务 `cancelled`，银行无变化 | 协议仍 `active`；银行操作 0；回复含「已经停下了」「银行那边没有变化」 | `test_sub_idm_02_user_cancel_leaves_the_mandate_alone` Passed |
| SUB-VFY-01 | 验证失败终止 | spec §4 SF06c；PRD §5.1 | 已过确认门，进入验证码后连续 3 次输错（000000） | 把优酷视频自动扣费退了 → 3 次错误验证码 | 任务终止，提示可重新办理 | `error.code=="VERIFICATION_TERMINATED"`、`upstream=="VERIFICATION_FAILED"`；回复含「验证码连续输错」「银行没有收到解约请求」；**严禁**出现胁迫话术（共享屏幕/挂断/客服电话）；银行操作 0；协议仍 active；再 resume 仍 failed | `test_sub_vfy_01_three_wrong_codes_end_with_the_verification_wording` Passed |
| SUB-VFY-02 | 高危阻断 | spec §4 SF06d；PRD T09 | 原话命中「客服让我/共享屏幕」胁迫观察 | 客服让我共享屏幕，赶紧把优酷视频退了 | 直接阻断并终止 | `error.code=="HIGH_RISK_BLOCKED"`、`upstream=="HIGH_RISK"`；确认单 0；银行操作 0；协议仍 active；回复给反诈指引（挂断+客服电话）而非承诺 | `test_sub_vfy_02_coercion_blocks_without_any_bank_call` Passed |
| SUB-VFY-03 | 验证强度边界 | spec §5.3/§8.4 | 注入非 LOW 风险裁决（策略实际只给 LOW/HIGH） | 把优酷视频自动扣费退了 | 用动作级 step-up，而非会话验证码 | 挑战 `purpose=="action_step_up"`、`required_methods==["code","mock_face"]`、带 6 项展示字段摘要；不降级为 `basic_identity`；银行操作 0 | `test_sub_vfy_03_non_low_risk_is_never_downgraded` Passed |
| SUB-RED-01 | 确认门红线 | spec §4 SF02 注；PRD §五 | sub_001 完整链路逐步核对 | 把优酷视频自动扣费退了 | 确认门与验证门逐一停留 | 各步银行操作数 `[0,0,0,1]`：确认前 0、已确认未验证 0、验证码已通过但未绑定 0；绑定后才 1；未绑定 resume 仍停在验证门 | `test_sub_red_01_no_bank_write_before_confirmation_and_verification` Passed |
| SUB-RED-02 | 口径边界红线 | spec §4 SF04/SF06；契约 §5.9 | 疑似项与已解约项各退一次 | 绿洲健身退订 / 喜马拉雅退订 | 都不进确认门 | 两任务确认单均为 0、银行操作 0；协议状态不变 | `test_sub_red_02_suspected_and_cancelled_never_enter_the_gate` Passed |
| SUB-RED-03 | 话术红线 | spec §2.3/§5.3；PRD §五 | 一轮内产生盘点、确认单、验证提示、成功回执、疑似引导、已退告知、高危阻断说明 | 盘点→退订 sub_001→绿洲健身引导→喜马拉雅幂等→云端网盘高危阻断 | 全链路 | 扫描 ≥15 条用户可见文本，**零**「会员可用至/还能用到/先退订再重新订阅/先解约再重签」；确认单与回执都含「从下一期（2026-10-24）起不再自动扣费，之前已经扣掉的钱不退」口径；仅被退项产生 1 张确认单 | `test_sub_red_03_every_output_keeps_the_wording_red_line` Passed |
| SUB-OBS-01 | 首启稳定性 | 票 05 审查观测项；票 08 `f202e5d` | 同一组装下连续首启 10 次盘点任务 | 帮我查查有哪些自动扣费 ×10 | 每次都应正常完成 | 10/10 `succeeded`；`SUBSCRIPTION_INTERNAL_ERROR` 次数 0；银行操作 0 | `test_sub_obs_01_repeated_first_start_is_stable` Passed |
| SUB-OBS-02 | 终止任务重复读取 | 票 05 审查建议；契约 §6.5 | 高危阻断后的 FAILED 任务 | 高危话术退订 → 终止后再读两次 | 只读终态，状态不倒退 | `get`/`resume` 三次均为 `failed`；载荷可 JSON 序列化；银行操作 0 | `test_sub_obs_02_terminal_task_stays_terminal_and_serializable` Passed |
| SUB-OBS-03 | 审计模块标签 | 票 05 审查建议 1（`f30cc1d`） | sub_001 完整链路后按事件类型核对 | 把优酷视频自动扣费退了 | — | `confirmation.changed`/`verification.changed`/`tool.*` 的 `module=="subscription"`；`security.decided` 的 `module=="security"` | `test_sub_obs_03_audit_events_name_their_module` Passed |

## 4. 三条红线

1. **确认门红线**：`SUB-RED-01` 逐步核对「未确认 / 已确认未验证 / 验证码已通过但未绑定」三个阶段银行提交均为 0，只有绑定后才发生 1 次；批量一键全退在 `SUB-DIS-01` 被拒。
2. **口径边界红线**：`SUB-RED-02` 断言疑似周期扣费（流水识别，非签约事实）与已解约项都不进确认门、不调 B30；`SUB-GUD-01` 断言外部渠道引导；`SUB-INV-02` 断言证据不足时不报「干净」。
3. **话术红线**：`SUB-RED-03` 对一轮内全部用户可见文本（消息、交互提示、选项标签、确认单字段）断言零禁用词，并断言确认单与回执只承诺「从下一期（…）起不再自动扣费，之前已经扣掉的钱不退」。

## 5. 稳定性观测（票 05 审查项）

票 05 审查报告过约 3/60 的偶发首启失败（`SecurityError` → `SUBSCRIPTION_INTERNAL_ERROR`）。本票用 [`stability_sample.py`](stability_sample.py) 在同一组装上连跑首启取样，定位到**底座审计脱敏缺陷**（票 08 `f202e5d`）：卡号掩码 `\d{12,19}` 会改写不透明引用 `sub-ref-<sha256[:24]>`，使审计证据键与事件引用不再一致。

| 观测 | 取样 | 结果 | 证据 |
|---|---|---|---|
| 修复前（`9741053`） | 150 次首启 | **16 次失败**（10.7%），全部 `SUBSCRIPTION_INTERNAL_ERROR`；门决策此前均为 `allow`，失败发生在审计写入 | [`evidence/2026-10-19/stability-pre-fix.json`](evidence/2026-10-19/stability-pre-fix.json) |
| 引用脱敏探针 | 20000 个 `sub-ref-<sha24>` | 修复前 **407 个被改写**（2.04%，如 `sub-ref-86e50149658661312a9e0b35 → sub-ref-86e****1312a9e0b35`）；修复后 **0** | [`evidence/2026-10-19/audit-ref-probe.json`](evidence/2026-10-19/audit-ref-probe.json) |
| 修复后（`f202e5d`） | 150 次首启 | **0 次失败**（150/150 `succeeded`） | [`evidence/2026-10-19/stability-post-fix.json`](evidence/2026-10-19/stability-post-fix.json) |

复跑观测：

```powershell
python evals/subscription/stability_sample.py --attempts 150 --label <标签> --out evals/subscription/evidence/<日期>/stability-<标签>.json
```

`SUB-OBS-01` 把同一性质钉进回归（每次评测跑 10 次首启，要求 0 次 `SUBSCRIPTION_INTERNAL_ERROR`）。底座修复属票 08 的 PR，本票不修改 `backend/`。

## 6. 证据

`evals/README.md` §六 的正本与索引都落在 [`evidence/<YYYY-MM-DD>/`](evidence/)：

- `subscription-platform-<UTC 时间戳>.json.gz`：本次运行的原始结构化报告（逐用例状态、逐条断言名与通过情况、失败清单、命令、解释器、`app_file`）；文件名唯一，不覆盖。
- `manifest.json`：追加式台账（标签、层、提交 SHA、脏文件、命令、状态分布、断言统计、报告解压后 sha256）。
- `manifest.md`：人读摘要（以上字段 + 本次运行逐用例表）。

生成方式见 §1 的 `SUB_EVAL_EVIDENCE`；未设置该环境变量时评测不写任何文件。

## 7. 替身与真实链路分界

| 组件 | 本评测集里的形态 |
|---|---|
| 模型入口 | **替身**：`RoutedPlanner` 直接返回目标 capability（真实 GLM 路由不在本票） |
| 模拟银行 | 真实 `MockBankService`：B29/B30、`bank_operations` 幂等、签约与流水种子（含共享账单流水） |
| 安全门与执行器 | 真实 `SecurityGate` + `DeterministicExecutor` + `ConfirmationService`/`SQLiteSecurityState` |
| 风险裁决 | 真实 `DemoSecurityPolicy`（含 `subscription.bank.cancel_subscription` 的 LOW/HIGH 分支与 fail-closed 证据） |
| 业务模块 | 真实 `SubscriptionEntry` 状态机与 checkpointer；单测里的 `FakeGate`/`FakeBank` 均未使用 |
| 审计与存储 | 真实 `AuditJournal`、`ApplicationStore`、`tool_operations`/`security_executions` |
| 时间 | 固定银行时钟 `2026-10-19 04:00Z`（北京 12:00），种子偏移与提醒窗口因此确定 |

未覆盖（明确不宣称）：真实 GLM 意图理解与线上模型稳定性、HTTP/前端（票 06）、真实反诈检测效果（安全评测）、两进程并发同一退订、`reminder_days`/`status_filter` 等入参参数化、银行侧失败码在平台层的表现。
