# v0.4 与动作绑定的可信风险输入（v04-risk-inputs）

> Status: In progress — 2026-10-19 Erwin 建立，来源 [Issue #160](https://github.com/DrErwin/hackerthon-bank-agent/issues/160)（Ringo 代码核查，转给 Erwin）
> Owner：Erwin（底座：`backend/app/agent_platform/`，必要时 `backend/app/api/`）
> 版本：v0.4
> 依赖方向：本组只提供「可信风险输入 + 检测器接缝」；风险识别算法与安全评测归 Ringo（`backend/app/security/`、`evals/security/`），消费方是 [v04-ringo-security/02](../v04-ringo-security/issues/02-real-risk-detector.md)。

## 1. 问题

现有安全门能消费后端风险事实，但生产装配的 `agent_platform/local_demo.py` 仍按「转出账户 + 收款人 + 金额」匹配配置里的 `transfer_fixtures`，直接返回预设信号与 checked_signals。它只能证明「系统如何响应一个给定等级」，不能证明「从真实请求与真实动作事实产生了这个等级」。

同时，原始请求文本虽然存在于 `api_tasks.intent_text` / API 消息任务，平台任务快照也有 `intent_text`，但没有一个按「可信主体、会话、演示轮次、任务及当前动作」关联的受控读取入口。把 SQL 直读或模型生成的身份当授权来源，都不成立。

## 2. 交付边界（本组）

1. **`v04-risk-inputs/01`（本组先做，agent_platform）**：服务端可信风险输入读取路径与检测器接缝。
   - 把原始请求（任务快照里的 `intent_text` + `request_id`）与当前动作的不可变事实（`transfer_snapshots` 绑定的参数）关联；
   - 绑定 user / session / demo_round / task / action / parameters_ref，跨主体、跨任务、跨会话、过期引用一律拒绝；
   - 收款人熟悉度、金额历史、环境三维事实各自携带 `known/unknown`、来源与检查范围；取不到的事实保持 unknown；
   - 给 Ringo 一个纯函数接缝：`RiskDetector = Callable[[RiskInputs], DemoRiskEvidence]`；离线可注入测试检测器；
   - 审计可观察：`security.decided` 的 `policy_version` / `rule_ids` / 脱敏 `evidence_refs` 可追踪，原始请求与认证秘密不进证据。
2. **`v04-risk-inputs/02`（依赖 v04-ringo-security/02，本组后做）**：生产装配改用「可信风险输入 + Ringo 检测器」，移除真实路径对 `transfer_fixtures` 的依赖；固定等级夹具只保留为流程对照。
   - 检测器未交付/未配置时 fail-closed（`RiskFactsUnavailable` → 安全门暂停），不退回夹具。

不新增公共契约字段；不改冻结业务规则（高风险终止、中风险双因子、低风险基础验证）；不动 `backend/app/security/` 与 `evals/security/`。

## 3. 本组内部口径（PM 待确认项）

以下为本组实现时采用的默认口径，**已按 Issue #160 要求列明，等项目负责人确认或调整**；调整只改常量与说明，不改接缝：

| 事项 | 本轮默认 | 说明 |
|---|---|---|
| 历史窗口 | 180 天 | 覆盖模拟银行种子里的历史转账（3 个月 / 5 个月前各一笔）；只读本人账户、经银行接入层 B08 |
| 收款人历史事实 | `saved` + `prior_outflows`；能进入写动作的收款人都已通过 B04 解析，所以 known 事实恒 `saved=true`；无法解析/读取失败 → unknown | 事实只描述数据，不判断「熟悉/陌生」：检测器用 `saved` + `prior_outflows` 自行区分「常用收款人」与「新收款人」（依据转账 PRD §附录 A 注，判定属识别规则） |
| 金额是否常见 | 窗口内该转出账户「转出 + transfer」历史样本为空 → unknown；否则 `amount_fen ≤ 2 × 历史单笔最大` 视为常见 | 阈值 2 倍为最小可解释口径，可由 PM 调整；不复制银行限额规则 |
| 设备/环境基线 | **unknown**（当前 API 无设备指纹来源） | 按 Issue #160「未知不推定低风险」：环境维度未知时不产出低风险结论，由安全门暂停。可选后续：API 增加受控设备标识（涉契约/前端），或检测器给出可解释的替代事实 |
| 数据来源 | 原始请求 = 平台任务快照；动作事实 = 平台参数快照；收款人历史/金额 = 模拟银行 B08 流水 + B04 收款人核验 | 检测器不直读 SQL；模型输出不能作为事实来源 |

### 3.1 安全侧待决（P0，阻塞 02）

`DemoSecurityPolicy.assess_risk` 要求证据覆盖全部 14 个信号维度才给等级（`security/demo_policy.py`），而本组要求未检查维度保持 unknown、不得写进 `checked_signals`。两者同时成立时，**如实报告事实的检测器会让每一笔转账写入暂停**（覆盖检查先于信号分类：合法对照到不了低风险，高风险也到不了 BLOCK）。Issue #160 的既定语义（未知事实暂停）本身正确，但生产可用性需要安全侧先决定：`checked_signals` 是否允许「已评估但事实 unknown」的维度、是否调整覆盖规则、是否先补可信设备来源，或明确接受「检测器接入后所有写入暂停」。该决定归安全侧/PM，本组不代签；在决定前，固定等级夹具只作流程对照。

## 4. 验收

- [ ] 服务端读取路径绑定完整，跨 user / session / demo_round / task / action / parameters_ref 与过期引用拒绝有回归。
- [ ] 三维事实都有来源与检查范围；取不到时保持 unknown，安全门按既有 `RiskFactsUnavailable` 暂停语义处理。
- [ ] 离线注入测试检测器可走通真实 HTTP 链路：真实原文命中高风险（终止、零资金副作用）、合法对照完成确认验证并只有一笔银行成功、未知事实暂停、跨任务引用拒绝。**合法对照与高风险证据明确标注为「流程对照」（检测器声明全维度覆盖，与既有夹具同级），不作为「合规检测器已可用」的结论。**
- [ ] `security.decided` 可观察策略版本、规则与脱敏证据引用；原始请求、账号原文和认证秘密不出现在审计证据中。
- [ ] 接缝说明（`backend/app/agent_platform/risk-inputs-seam.md`）交付并通知 Ringo；生产装配切换票（02）在 Ringo 检测器交付后完成。

## 5. 非目标

- 不做风险识别算法、关键词库与阈值组合（Ringo 的 security 目录）。
- 不重开 v0.3 历史证据，不改历史报告。
- 不处理 Issue #164（订阅声明与安全预期共用对象，转给 Ringo 的 security 目录）。
