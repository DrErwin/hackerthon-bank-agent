# 可信风险输入接缝（Issue #160 / v04-risk-inputs/01）

给安全目录的检测器作者（Ringo）看的接缝说明。本文件与 `risk_inputs.py` 是接口事实源；检测器的识别规则、风险等级映射与评测仍在 `backend/app/security/`、`evals/security/`，不在本接缝内。

## 1. 接缝是什么

```python
from app.agent_platform.risk_inputs import RiskDetector, RiskInputs, TrustedRiskInputs

resolver = TrustedRiskInputs(application, snapshots, gateway)   # 装配时构造一次
inputs = resolver.resolve(context, action, declaration)          # 每次风险裁决前调用
evidence = detector(inputs)                                      # 检测器实现；返回 DemoRiskEvidence
```

- `context: ExecutionSecurityContext`、`action: ActionDescriptor`、`declaration: CapabilityDefinition` 都来自统一安全门，不由模型或前端提供。
- 检测器只接收 `RiskInputs`；它不读 SQL、不读任务快照、不调用银行。服务端读取全在 `TrustedRiskInputs` 内完成。
- 返回值仍是既有 `DemoRiskEvidence`，`DemoSecurityPolicy.assess_risk` 的分类与三档处置不变。

## 2. 绑定与拒绝（fail-closed）

`resolve` 先把原始请求和动作事实绑到同一个可信范围，任何一项不符都抛 `RiskFactsUnavailable`（安全门按既有暂停语义处理，不会降级成低风险）：

| 规则 id | 触发 |
|---|---|
| `risk-input-task-binding-required` | 任务不存在、不属于当前 user/demo_round、任务 `session_id` 与上下文不一致、任务已终态 |
| `risk-input-request-binding-required` | 任务快照缺少 `request_id` 或 `intent_text` |
| `risk-input-action-binding-required` | 参数引用过期/越权：`transfer_snapshots` 中 user、demo_round、task、action、operation、action_revision 任一项与上下文不符；参数形状不合法 |
| `risk-input-action-unsupported` | 非 `bank.submit_transfer` 写动作（本接缝暂只覆盖转账写入；订阅退订沿用其专用事实） |

`evidence_ref = risk-inputs-<sha256(...)[:24]>`：由 user/session/demo_round/task/action_name/parameters_ref/operation_id/action_revision、`request_id` + 请求文本哈希与三维事实确定性计算，**不含原文**。事实状态不变时同一动作得到同一引用（`run_id` 不参与摘要：恢复会换 run，但可信范围与输入没变）；两阶段之间银行流水发生变化时引用会变，这是期望行为。

## 3. `RiskInputs` 字段

| 字段 | 含义 |
|---|---|
| `user_id / session_id / demo_round_id / task_id / run_id` | 本次裁决的可信范围（`run_id` 仅信息用途，不进摘要） |
| `request_id / request_text` | 原始请求：任务快照里的 `request_id` 与 `intent_text`；**仅内存可用，不得写入日志、审计、报告或模型上下文**（`repr` 已隐藏） |
| `action_name / parameters_ref / operation_id / action_revision` | 当前动作身份 |
| `action_facts` | `transfer_snapshots` 解析出的不可变参数（`payer_account_id / payee / amount_fen` 等）；同上，仅内存、`repr` 已隐藏 |
| `facts` | 三维事实（见下），`fact(name)` 取用 |
| `evidence_ref` | 脱敏不透明引用；放进检测器返回的 `DemoRiskEvidence.evidence_ref`，即可在 `security.decided` 的 `evidence_refs` 里追踪 |

## 4. 事实与 unknown

每个 `RiskFact` 都有 `name / status(known|unknown) / source / scope / value`。**unknown 表示该维度没有检查：检测器不得把它当作安全信号，也不得把未检查维度写进 `checked_signals`。**

| 事实 | 本轮来源 | 值 |
|---|---|---|
| `payee_history` | `mock-bank:b04+b08`（B04 收款人核验 + B08 本人账户流水） | `known`：`{saved: bool, prior_outflows: int}`；收款人无法解析、核验失败或流水读取失败 → `unknown` |
| `amount_history` | `mock-bank:b08`（本人转出账户近 180 天 `outflow + transfer` 金额） | `known`：`{amount_fen, sample_size, baseline_max_fen, multiple, usual}`；无样本/读取失败 → `unknown` |
| `environment` | `platform:no-trusted-device-source` | **固定 unknown**：当前 API 与任务快照没有设备指纹来源，不假造「常用设备」 |

事实只描述数据，不给风险结论：`payee_history` 不再自带 `familiar` 布尔值，检测器用 `saved` + `prior_outflows` 自行区分「常用收款人」与「新收款人」（当前银行路径下能进入写动作的收款人都已通过 B04 解析，因此 `known` 事实恒 `saved=true`；手工首次收款人无法解析，只能 `unknown`）。

### 4.1 必须先由安全侧决定的接口冲突（P0）与 PM 处置

`DemoSecurityPolicy.assess_risk`（`security/demo_policy.py`）要求证据覆盖**全部 14 个信号维度**才给等级，否则 `RiskFactsUnavailable` → 安全门暂停。而本接缝要求未检查维度不得写成 checked。两者同时成立时：**如实报告事实的检测器会让每一笔写动作暂停**（合法对照也到不了低风险，高风险也到不了 BLOCK——覆盖检查先于信号分类）。当前平台还缺 `rapid_account_changes`、设备等来源，无法靠补事实绕过。

Issue #160 的既定语义就是「取不到的事实保持 unknown，由安全门暂停」，所以暂停本身是正确行为；生产可用性取决于安全侧把以下之一写成决定：

1. `checked_signals` 是否允许「已评估但事实 unknown」的维度，以及此时 unknown 如何不产出安全信号、低风险如何可达；
2. 或调整 `DemoSecurityPolicy` 的覆盖规则（允许部分覆盖 + unknown 处置）；
3. 或先补可信设备/环境事实来源（涉 API/契约/前端，属 PM 决定）；
4. 或明确接受「检测器接入后所有转账暂停」。

**2026-10-19 PM 决定（Erwin 本人，方案 A）**：本项目是黑客松 Demo，**不接真检测器到生产装配**——演示的风险等级继续由 `local_demo` 的固定等级夹具给出（流程对照），Ringo 的真实检测器只在离线评测层使用，**不采集设备信息**；生产装配与夹具移除（[v04-risk-inputs/02](../../../.scratch/v04-risk-inputs/issues/02-detector-assembly-and-fixture-removal.md)）转为 deferred（v0.5），上述 1/2 的映射决定随之留到 v0.5。因此本接缝在 v0.4 的定位是「已交付、可复用、未接入演示」。

测试按用途分开标注：`flow_control_detector`（声明全维度覆盖，仅流程证据）与 `fact_backed_detector`（只声明事实支持的维度，如实暂停）。

演示口径（180 天窗口、2 倍金额阈值）在 [v04-risk-inputs spec](../../../.scratch/v04-risk-inputs/spec.md) §3；设备来源已按 PM 决定 A 不采集。调整只改常量，不改接缝。

## 5. 检测器实现注意事项

1. 导入 `app.agent_platform.risk_inputs` 时不要同时 import 全平台：`app.agent_platform/__init__` 会装载 `transfer_runtime`。把 import 放在检测器模块的**函数内**，或先 `import app.security` 再导入（安全包已完成初始化，不会循环）。
2. 检测器输出的证据：`source` / `source_version` 填检测器版本；`evidence_ref` 用 `inputs.evidence_ref`；`signals` / `checked_signals` 只填实际检查过的维度（见 §4.1）。
3. 离线注入用法见 `app/agent_platform/test_risk_inputs.py`：真实 HTTP / harness / 安全门 / 执行器 / 审计 / 模拟银行，仅检测器是替身。**真实检测器请参照 `fact_backed_detector()` 的 checked 口径（只声明事实支持的维度），不要照抄 `flow_control_detector()` 的全维度声明**——后者与既有夹具同级，只用于流程对照。
4. 生产装配（`local_demo.build_runtime`）的接入属于 `v04-risk-inputs/02`：装配层只做「`resolve` → `detector`」，不写识别规则，也不回退 `transfer_fixtures`。

## 6. 已知边界

- 手工收款人不在银行已存收款人内时无法稳定匹配历史对手方，故 `payee_history` 为 `unknown`（fail-closed）；当前银行路径下这类收款人会被预检查拒绝，正常不会进入写动作。
- 受控收款人引用（`kind=reference`）当前不在写动作快照里出现；一旦出现会因参数形状校验失败按 `risk-input-action-binding-required` 整体暂停。
- 订阅退订的风险事实仍走 `subscription_risk_evidence`，不在本接缝内。
- 本接缝不产生风险等级；等级仍由 `DemoSecurityPolicy` 按既有信号集合判定。
# 父任务风险来源（平台19）

跨场景子转账的内部 `capability:step` 标记不作为用户原话。`TrustedRiskInputs` 用可信 `source_task_id`、同用户/轮次的持久父子关系及 step/plan 版本交叉核实，读取真实 cross 父请求。`RiskInputs.request_source_task_id` 表示已核实的来源任务（普通根任务为自身），默认 `None` 的旧构造不代表来源已核实。`request_id` 对应该来源原请求；不以这个字段代替确认或验证。

现有 `RiskConversation` 保留同任务跨会话的父/子文本跟进；普通有 UUID 的受控文本续做按原请求去重。专用明细原文不从表单或聊天复制到此路径。旧批次没有捕捉到的跟进不能补造，不能因重启或迁移宣称历史完整。原话只送进程内检测器，公开 evidence_ref 仍为包含来源任务的摘要。缺失/异主体/异关联/版本不符继续暂停；不新增风险事实、阈值或付款权限。
