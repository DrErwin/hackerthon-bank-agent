# S01 单项订阅入口只读归因（2026-10-25）

Status: diagnosed_reviewed — 已定位兼容入口路径，独立缺陷仅登记候选，未授权实施
Owner: Erwin授权执行对话
Source issue: [Issue #301：真实减支目标误入单项退订](https://github.com/DrErwin/hackerthon-bank-agent/issues/301)

## 给业务负责人的结论

这次没有发生退订。原真实S01的主失败是完整减支目标被模型选进单项退订入口，属于平台完整生活目标路由线；不能把一次清单查询的succeeded当成S01完成。本对话不改平台或prompt。

“模型选cancel却返回list”的程序原因已可确定：聊天路径传旧StartTransferInput，两个订阅能力共享同一个工厂；模块不以候选能力名固定动作，而重新按原话的取消词判断list/cancel。原话没有命中该词表，于是进入list并终态返回。**这不是已实现的退订澄清**：结果没有input交互、没有待选对象，allowed_actions为空。

旧信封和模块再解析本身是原票明示、已接受的兼容设计，不能因“没有类型化”就宣布其违反旧规格。也不能只凭这次含完整生活目标的原话认定所有list回退都错。

但独立的明确单项反例支持另立订阅候选：**“请帮我停止优酷的自动扣费”**经旧信封仍被处理为list/succeeded；同文经SubscriptionCancelInput会进入原确认单，均未写银行。这说明旧入口把“未识别到取消词”直接当作“明确只读”的二分回退存在明确办理意图被静默降级的问题。它是订阅兼容入口的独立候选缺陷，不是本次真实S01唯一根因，也未在真实模型/银行/页面重验。

最小候选为[v05-s01-subscription-diagnosis/01：明确单项停止扣费不得静默降级为盘点](issues/01-untyped-action-clarification.md)，仅modules/subscription目录，Status为proposed，等待中控实施信号；此轮不修复。

## 固定材料与真实性

- 研究worktree：`C:/Users/57652/.codex/worktrees/v05-s01-subscription-diagnosis/hackerthon-bank-agent`，本地分支`codex/v05-s01-subscription-diagnosis`。
- 观察证据固定[PR300 head31e995e75c12af57e05ae8cc9cda56b3da2d9693](https://github.com/DrErwin/hackerthon-bank-agent/pull/300)，产品main2a070b9cf992a109d8b54718a49dc3e3b56bd236；两者backend tree相同：`83b766fd3c15bec6939511049ec4b8ef1e3adb3c`。本次后续提交仅本组诊断材料。
- 已完整读取[真实失败报告](https://github.com/DrErwin/hackerthon-bank-agent/blob/31e995e75c12af57e05ae8cc9cda56b3da2d9693/evals/cross/evidence/2026-10-25/s01-live-20261025-01.md)及原json.gz；解压JSON SHA256核对为`95cf45a276d56bd5812467e5bf616289499d76b93d09ce2081a85ce630a75f87`，未改原文件。
- 原样本只真实运行一次：“最近钱怎么花得快，帮我处理不用的扣费”。原JSON的input与task.snapshot.intent_text一致；model.request含cross.start_task，model.response为propose_transfer(capability_name=subscription.cancel_subscription)，invalid_tool_calls为空；模型请求/响应各1、异常0。
- 持久task的proposal.capability_name与snapshot.capability_name均为cancel；**snapshot.selected_capability为null**，不把它误写成固定cancel字段。模型候选已参与平台鉴权和选工厂，并非平台完全丢掉候选；只是未将其作为订阅内部动作模式传入。
- 原result：succeeded、data.action=list、interaction=None、allowed_actions=[]、error=None；cross关系0，4次只读工具（账户1、签约1、流水2），银行写请求/原操作/结算效果均0，确认0、验证0。这些是旧真实样本证据，不是本次新调用。

## 确定的代码链

| 接缝 | 固定源码位置 | 实际作用 |
|---|---|---|
| 选择能力 | [harness.py](../../backend/app/agent_platform/harness.py):743–756 | 用proposal.capability_name鉴权、取注册与工厂；随后统一构造StartTransferInput，只有request_id/intent_text及转账字段，没有订阅动作模式 |
| 注册 | [registry.py](../../backend/app/agent_platform/registry.py):57–71；[subscription/entry.py](../../backend/app/modules/subscription/entry.py):347–358 | register_module为模块两能力使用同一factory；工厂构造同一种SubscriptionEntry，不传capability_name |
| 逻辑输入 | entry.py:103–131 | SubscriptionListInput直接list；SubscriptionCancelInput直接进入取消流程（只是意图及范围，不是执行授权）；旧StartTransferInput由wants_cancel决定模式 |
| 词表判断 | entry.py:36–37、53–56、128–131 | 只要包含既有取消词即true，否则直接list；原S01句和明确“停止”句都为false |
| 完成盘点 | entry.py:187–198；[service.py](../../backend/app/modules/subscription/service.py):392–399 | inventory后list_task给action=list、succeeded、interaction=None、allowed_actions=[]，不会进入_cancel_step |
| 取消消歧及安全门 | entry.py:207–276；service.py:276–312、422–437 | 只有cancel路径才resolve_cancel；目标不清/多候选先waiting_input，选定银行有效项后最多先到确认/验证；ALLOW后才可执行 |

因此capability是候选路由信息，既不代表用户已选哪笔，也不代表已经确认、验证或获准执行。把模式改成cancel不等于可以跳过任何一步；本轮没有这样改。

## 原规格实际规定与缺口分类

1. [v04-subscription/03：订阅模块](../v04-subscription/issues/03-subscription-module.md):53明确入口收到StartTransferInput，再转逻辑List/Cancel输入；[v04-subscription/05：平台接线](../v04-subscription/issues/05-platform-subscription-wiring.md):64的已接受差异进一步说明不从模型提订阅槽位，模块按原话确定性解析。因此不能把“模型没有给出类型化请求/槽位”本身判为新独立故障。
2. [原spec](../v04-subscription/spec.md) US-1/US-2/US-4与[PRD SOP-2](../../docs/prd/05-订阅代扣管理-PRD-2026-10-19.md):106–118规定：点名停止未来扣费属于退订语义，先认对象、展示后果；无目标或多候选让用户选择，不能默认第一笔，随后仍需确认及基础身份验证。03票:44/47也分别要求WAITING_INPUT或确认单。
3. [SubscriptionCancelInput](../../backend/app/contracts/subscription.py):198–211明确“省略目标必须消歧”。类型化入口同文无目标实际返回waiting_input，说明取消消歧/确认链已经存在，不需要把原S01文字强行转成可执行取消。
4. **不是原SOP缺少对象选择/确认规则**；这些规则已经足够明确。缺少的是兼容入口对“未识别”和“明确只读”的区分/覆盖，原规格并未明示批准所有含糊处理目标都终态盘点。原S01句本身仍是跨场景路由失败；明确停止单项的离线反例才支持独立订阅缺陷候选。修复不能仅补一个“停止”词或原S01固定答案，也不能把模型候选当授权。

## 最小离线复现与结果矩阵

本组[reproduce.py](reproduce.py)直接调用真实公开注册工厂/SubscriptionEntry/Service，但端口只使用既有test_subscription中的FakeBank、FakeGate、MemorySaver，全部数据内存隔离，不创建MockBank、不访问银行网关、网络或真实模型。脚本检查原样本终态list症状及全部fake_cancel_calls=0；它是观测探针，不是已批准产品回归期望，更不把10行观测冒称10个测试通过。产物见[probe-result.json](probe-result.json)（提交版仅规范LF换行；原输出另以本地忽略raw.log保留）。

```powershell
# cwd: 本worktree/backend；先显式保证app源码来自本树
$diagnosisRoot = (Resolve-Path ..).Path
$env:PYTHONPATH = (Join-Path $diagnosisRoot 'backend') + [IO.Path]::PathSeparator + $diagnosisRoot
$diagnosisPython = 'D:/hackerthon-bank-agent/backend/.venv/Scripts/python.exe'
& $diagnosisPython ../.scratch/v05-s01-subscription-diagnosis/reproduce.py
```

| 观察 | 请求 | 结果（全部fake写调用0） |
|---|---|---|
| 原话，取cancel注册 | StartTransferInput | mode=list、succeeded、action=list、无交互/门检查 |
| 同原话，取list注册 | StartTransferInput | 同上；证明共享工厂不绑定能力模式 |
| “把优酷视频的自动扣费退了” | StartTransferInput | mode=cancel、waiting_approval/confirmation，门检查1 |
| “帮我退订一项自动扣费” | StartTransferInput | waiting_input，2个Fake有效项可选，门检查0 |
| **“请帮我停止优酷的自动扣费”** | StartTransferInput | **list/succeeded，无交互**；明确办理意图静默降级的单项反例 |
| 同一明确停止句 | SubscriptionCancelInput | waiting_approval/confirmation，门检查1，未执行 |
| “帮我查查有哪些自动扣费” | StartTransferInput | list/succeeded，读路径正常 |
| 原S01原话，未给目标 | SubscriptionCancelInput | waiting_input，2个Fake有效项可选，不自选/执行 |
| 原S01原话，指定sub_001 | SubscriptionCancelInput | 仍先confirmation，门检查1，不执行 |
| 原话为“退订”但输入类型为List | SubscriptionListInput | list/succeeded；结构化请求动作优先，文字不自动转写 |

还运行了11个**既有且未修改期望**的Fake端口局部测试：list_mode、cancel_full_flow_confirmation_then_verification、batch_refusal、text_disambiguation、typed_cancel_target、typed_list_filters、intent_helpers、suspected_no_confirmation、already_cancelled、cancel_before_confirmation、high_risk_block。具体原节点名/文件见[existing-tests.xml](existing-tests.xml)和[日志](existing-tests.console.txt)，**11 passed**，控制台0.40s，XML suite0.266s。命令仅枚举这11个test_subscription.py节点，没有运行test_subscription_ports.py真实银行集成、CI或全量。

既有完整取消测试只是FakeGate/FakeBank内的确认→验证→一次fake取消，不能当作本次真实银行退订验证。探针与既有测试也不能替代修复后的新真实S01批次。

| 本组产物 | SHA256 |
|---|---|
| reproduce.py | 8e221953179408a74bed46c3b6af3f6bcfa9be17574d0f31c0bc976687ada426 |
| probe-result.json | 25760068953f7b5d05340dfc732897565496efc55626a8992585f1ab86d5615e |
| existing-tests.xml | 1eed5c9b0e33db396cbe96a628b76cf67bc4a15d66998f8610ecf67dcd9a2fb1 |
| existing-tests.console.txt（原控制台仅规范LF） | b4cf5fa27b26e4dc5f5cb23a53f424e67ce09d580ef46740ff53639acac198c3 |
| existing-tests.log（本机忽略原日志） | 2ed4aabf8fdf52c24e015228ea3bbbc62dd8548c7cc037f640e4949b1d9924d1 |

## 应有行为与具体责任

| 请求/阶段 | 业务上应有的行为 | 责任 |
|---|---|---|
| 完整“找原因并处理不用扣费” | 由平台正确选择完整cross生活目标，保留账单依据、清单和逐项子任务；不强制所有订阅请求走cross | agent_platform原执行线，关联Issue301；本票不改 |
| 明确只读盘点/续费查询 | list成功代表查询完成，不代表退订；不产生银行写、确认或验证 | subscription现有S01 |
| 明确停止单项 | 先核对本人银行有效项，缺信息/多候选先选择；唯一项也先确认后果，再按原验证/执行器办理 | subscription独立候选01 |
| 已明确取消但对象不明/批量 | WAITING_INPUT，逐项选择，不默认第一笔、不批量全退 | 原SOP-2/typed路径已具备；候选须保持 |
| 仅含“处理不用的扣费”等不确定表达 | 不能凭模型cancel候选推定已选择/已授权；完整目标交平台路由。不在本诊断自行裁定所有含糊文本都应取消或都应终态盘点 | 平台/中控定义范围；需要额外产品选择先提交具体方案 |
| 目标明确但尚未确认/验证 | 仅等待原安全步骤；模型/聊天肯定词不是确认授权 | subscription执行门沿用；不改security/#160 |
| 页面“已办结” | 原任务确为succeeded/list，解释了显示；不能据此改前端掩盖S01未完成 | 前端本轮不修；如有展示产品需求另派 |

## 候选与本轮停止点

候选01只处理已明确的单项停止扣费被legacy入口静默降级，不承担完整S01路由修复。候选的行为验收应遵循已冻结SOP，不硬编码原失败句/答案，不拼接个案prompt，不改账户/签约事实、权限、安全门或公共契约。若所选方案需要平台提供新的动作/类型信息，应由平台另票提供，不能在模块票跨目录补。

此轮采用diagnosing-bugs的脱敏、固定基线、最小观测与假端口对照；不进入修复/回归改写阶段，因为用户仅授权诊断/必要规划。没有修改产品或模型prompt、原期望、平台/前端/安全、原PR、组合证据和共享跟踪；不新建GitHub Issue/代码PR、不合并、不运行CI或全量。原真实失败和“一次样本”的范围保持不变。后续等待中控给候选实施信号，不能把候选状态自动设为ready-for-agent。

## 独立审查

Standards/准确性与Spec/结论两个独立子代理最终均PASS，必须修正0：核对原gzip及哈希、固定源码与已接受旧信封差异、S01主路由与单项候选分开归因、10行Fake端口观测和11项既有测试、LF规范化/哈希、候选proposed状态及安全/目录边界，并确认产品/原证据零差异。两代理只读，未启动额外测试、真实模型或银行。审查通过仅说明归因与候选范围准确，不代表授权实施、缺陷已修复或E2E接受。

实施副本来源：本报告及旧probe/XML从本地74da8d9按本组路径复制；原观察数据和断言保留，未重跑覆盖。未合入的PR300报告仅改用固定31e995e链接；原诊断worktree不修改。后续修复证据另写implementation.md。
