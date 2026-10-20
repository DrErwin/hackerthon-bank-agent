# security —— 安全底座

## 2026-10-20：L02 与订阅敏感边界补充

`bills.detect_anomalies` 按 Issue #187 以安全侧独立快照收录，继续使用 `bills.read`、只读重试和本人当前轮次作用域。未知账单能力、声明漂移及越权作用域仍默认拒绝。

Issue #191 将公开退订能力及私有银行退订工具统一按 `SENSITIVE` 复核。普通退订仍沿用已定的按钮确认和会话级基础验证；放行时必须生成脱敏授权快照，快照写入失败返回 `PAUSE/AUDIT_UNAVAILABLE`。订阅读取能力保持 `READ`，不生成授权快照。策略版本按主线 `v04-local-demo-read-N` 序列升为 `v04-local-demo-read-4`（本次变更：转账 6 条、订阅 6 条共 12 条声明改为安全侧独立冻结副本，与业务模块声明全字段全等比较）。

本轮合并前复跑：`app/security` 288 passed、`evals/subscription` 51 passed、后端全量 1145 passed。真实执行器回归证明授权快照先于银行处理器，快照失败时处理器零调用；真人签核、真实模型复跑及 CI 结果分别记录。

2026-10-20补充：#164声明冻结重新整理为独立主线分支，保留#184已合的L03快照，转账与订阅预期从业务可变对象分离；未知能力仍默认拒绝。合并前复跑 `app/security` 288 passed、`evals/subscription` 51 passed、后端全量 1145 passed，范围及初始版本断言修订见[module-declaration-review-2026-10-19.md](module-declaration-review-2026-10-19.md)。原#165关闭但未合入；本独立分支已合入 main（#164/#191），合并为 PM 代行、非 Ringo 本人审查，真人批准另记。

归属：安全（Ringo）。

放什么：策略、统一工具执行器、确认门、权限枚举、**审计规则**（记什么 / 脱敏 / 谁可看；写入与查看端在 `../audit/`）。开发原则见 [02-security-platform](../../../docs/principles/02-security-platform.md)。

边界：不编写业务 SOP，不复刻银行限额 / 余额 / 风控规则，不替代银行做交易最终判定。

## v0.3 最小执行门

`gate.py` 提供普通转账纵向链路所需的四个接缝：

- `ToolRegistry`：注册工具时校验权限、操作等级、副作用和逐动作确认策略；未注册工具默认阻断。
- `ConfirmationService`：只接受结构化按钮答案，绑定服务端用户、会话、轮次、任务、动作版本和参数快照；确认有效期固定为一小时，重复同答案返回原决定。关键内容改变须使用新操作编号和递增的动作版本，旧确认随新确认失效。确认版本和执行认领保存在应用 SQLite 中，服务重启后仍然有效。
- 过期确认的作答与执行认领会先把 `expired` 状态提交到应用库，再向调用方返回 `CONFIRMATION_EXPIRED`；过期动作不会领取资金执行记录。
- `SecurityGate`：先核对可信作用域和任务状态，再检查动作绑定、后端风险、当前确认和银行验证记录，返回冻结契约的六种裁决之一。确认和验证交互只引用由后端创建的真实记录。低风险资金动作需要同会话基础验证，中风险只接受绑定当前动作版本的验证码与模拟人脸双因子记录，高风险在安全状态中持久标记任务终止。
- `DeterministicExecutor`：只在执行阶段调用资金处理器；实际参数只按 `parameters_ref` 从后端受控快照读取，调用方不能在确认后替换参数；读取参数后重新检查安全状态，提交前以同一数据库事务核对任务终止状态、认领操作并锁定确认。重复请求和服务重启只按原操作编号回查银行结果；`not_found` 与查询失败都保留待核实状态，不能重新调用资金处理器。

风险判断、权限与资源归属、任务终止状态、确认与验证记录创建、银行验证记录及其源挑战读取、脱敏授权快照保存和安全裁决写入均由后端注入的确定性回调提供。`summary_validator` 必须用与确认和实际执行相同的受控参数快照核对中风险验证摘要中的金额与收款人；安全门同时核对摘要展示项与确认展示项，并在放行前复核已通过验证的源挑战。模型、聊天文字和前端布尔值不能直接生成这些可信事实。敏感动作在授权快照或裁决记录写入失败时暂停，不调用工具。

任务取消与执行认领须使用同一应用数据库事务锁或等效同步；认领事务内的 `task_state_resolver` 只读当前任务状态。若任务状态存于独立系统，接入方须提供等效的原子状态核对，不能只依赖事务前的复查。

当前实现只覆盖票 #07 的普通转账最小门槛；限定释放、完整策略检测器和后续业务安全规则仍按各自里程碑实现。本实现尚需 Ringo 的安全评测与代码审查，不能据此标记票据完成。

## 本机演示权限与风险回调

安全裁决的 `policy_version` 同时记录安全门版本与风险策略版本（以 `+` 连接）；日志写入失败返回暂停时，仍保留当次命中规则、版本和事实引用，且不提交资金。

`DemoSecurityPolicy` 提供票 03 所需的回调：它只允许配置的演示用户和服务端当前轮次，逐项匹配现有 `MANIFEST` 与 `PRIVATE_TOOLS` 声明及其权限；人脸作答还必须来自单独配置的管理身份。管理身份验证仍由调用它的服务端组合负责，不能从前端字段推导。

风险事实必须由服务端注入的 `risk_facts` 读取器提供，并带来源、版本和证据引用；每个风险信号维度都须有明确的检查结果，覆盖不全时暂停。策略按转账 PRD 01 §9.2 分类：任一高风险信号判高；否则任一中风险信号判中；只有常用收款人、常用设备、常见金额范围和清楚表达四项证据齐全，才判低。不设置金额阈值，也不从聊天文字推测事实。成功分类以 `RiskAssessment` 返回，现有 `SecurityGate` 将策略版本、分类规则和来源版本/证据引用写入裁决；事实缺失时会记录具体规则编号，并暂停为依赖不可用。高风险仍由该安全门终止任务，中风险仍走既有双因子验证。

**场景 05 订阅代扣退订的例外（2026-10-19）**：`subscription.bank.cancel_subscription` 只分两档——命中 `_HIGH_RISK_SIGNALS` 判高并直接 `BLOCK` 终止；其余一律判低，走「确认按钮 + 会话级基础身份验证码（`purpose="basic_identity"`、`scope="session"`）」，**不启用中风险双因子/模拟人脸**（PRD §五：退订是止损停扣、不是资金转出）。该分支仍保留 `authorize_tool`、证据类型与 `checked_signals` 全覆盖的前置校验（fail-closed 不变）。

当前风险评估通过回调注入，仓库还没有覆盖这些 PRD 信号的可信运行时事实读取器。API 已有独立管理身份登录；票 04 需要把本策略接到现有管理会话路径。当前票提供并测试策略回调和可重复分类样例；运行时事实接入由票 04 提供。在票 04 接入可信事实前，缺少事实的普通请求会暂停，不会被假定为低风险。样例测试证明分类规则，不代表诈骗检测覆盖或真人安全批准；Ringo 审查仍是安全票的必要门槛。


修复票 `v03-transfer-eval-fixes/06`：安全门保存已签发的脱敏验证挑战来源，每次敏感操作前从银行接入端重新核对该任务的可信状态。`failed` 或中风险 `expired` 形成持久终止标记及带挑战证据的BLOCK；基础前两错和基础验证码过期不被永久终止。源事实查询异常保持PAUSE，不按异常文案判断输错或超时。旧会话来源仅用于阻止原任务，不能授权新会话。测试：`python -m pytest app/security/test_gate.py app/security/test_verification_terminal.py -q`，25项门测试及8项真实平台/银行终止与技术暂停测试通过；六类终止均零流水且重建后不复活。HTTP集中联调、TF-VFY矩阵对照及真人安全审查仍待。

重发中断窗口依赖 `v03-transfer-eval-fixes/05` 的银行类型化终止事实（PR #53）：安全门只接受同用户/轮次/任务的真实VerificationChallenge终止状态，异常字符串不形成终止。组合定向34通过（25门测试、9生命周期/恢复测试），包含重发落库后应用未登记即关闭、替代挑战三错、重建仍failed且零流水。

## v0.4 本人账单读取（Issue #137）

按 [PM 10-18 临时口径](https://github.com/DrErwin/hackerthon-bank-agent/issues/137#issuecomment-6250123462)，本人账户读取为 LOW，免确认及免验证。`bills.read` 仅准入 `bills.summarize` 和两条 `bills.bank` 读取，API 负责当前登录及任务归属，银行逐账户核验可信用户身份；该权限不包含敏感导出或新业务写操作。

账单预期声明固定在安全目录，逐项全等比较。业务模块修改六项安全属性、输入输出模型引用或处理器引用后，原白名单拒绝该声明，须新安全审阅；业务对象的原地修改同样不能改写安全预期。该策略返回带版本与规则依据的读取分类，跳过转账演示夹具。转账仍要求原有可信风险事实，缺失事实继续暂停。

审计口径要求采用参数摘要与结果引用；当前实现仍记录原始参数与完整银行结果，具体边界及已知落盘缺口见 [安全意见](bills-read-security-review-2026-10-19.md) §3。[Issue #145](https://github.com/DrErwin/hackerthon-bank-agent/issues/145)由账单负责人整改，本次安全目录改动不代替该修复，也不构成真人签核。

## v0.4 L03 账单报告能力收录（Issue #177）

`bills.generate_report`（L03 月度/年度本人账单报告）按 #149 的「安全侧独立冻结快照」口径收录：安全目录保存一份从该模块发布（`modules/bills/manifest.py` 的 `REPORT_MANIFEST`）抄来的固定声明，**不 import、不引用业务对象**；`authorize_capability` 仍逐字段全等比较，声明漂移、未知能力和业务对象原地改写一律拒绝。

- 放行：当前轮次的演示用户（与 L01 相同作用域）调用 `bills.generate_report`；它是 `bills.read` 权限内的只读能力（`side_effect=False`、`confirmation_policy="none"`、`retry_policy="read_only"`），不触发确认/验证，也不产生资金或导出写入。
- 拦截：越权用户、过期轮次、任何字段漂移的声明，以及未审阅的 L02 `bills.detect_anomalies`、敏感导出等未收录能力。本次未改 `authorize_capability` 的全等比较与用户/轮次作用域逻辑，只新增一条已审阅声明，也没有批量放行账单能力；`_permissions` 与 `assess_risk` 未改。
- 切换时点：合并后真实报告能力才可通过安全门（平台侧注册已由 [PR #178](https://github.com/DrErwin/hackerthon-bank-agent/pull/178) 完成）；放行集合变化，`policy_version` 升为 `v04-local-demo-read-2`，安全裁决记录（`SecurityDecision.policy_version`）携带新版本；`ConfirmationRecord` 本身不含策略版本字段，L03 也不触发确认。
- 验证：`app/security/test_bills_report_policy.py` 17 项（合法放行、九个声明字段〔不含 name〕逐一漂移拒绝 + name 改名经未知能力用例拒绝、冻结副本与模块对象独立、未知能力默认拒绝、用户/轮次越界拒绝）；`app/security` 全量 117 passed。另有真实 `DemoSecurityPolicy` + 已注册 L03 运行时的切换证据：改动前 `authorize_capability(...) == False`（`v04-local-demo-read-1`），改动后 `True`（`v04-local-demo-read-2`），同轮次 L01 仍为 `True`，越界用户/轮次仍为 `False`。真实 local-demo HTTP 栈实测：改动前 L03 能力被安全门拒绝、不建任务；改动后任务 `succeeded`、`module=bills` 并产出 `report_id`。

**记录边界**：本单因 [#164](https://github.com/DrErwin/hackerthon-bank-agent/issues/164) 在途、由 PM 指派的其它会话代做，属 **PM 代行、非 Ringo 本人审查**；AI 复核不等于真人专业签核，Ringo 本人的安全签核仍缺，不得据此记作已获安全签核。**合并决定与范围**：PM（Erwin）2026-10-20 决定由其它会话代做并按「只改 `backend/app/security/`、一票一目录一 PR」范围合入（[PR #184](https://github.com/DrErwin/hackerthon-bank-agent/pull/184) squash `3f9996c`）；该条是 PM 的代行/豁免记录，不改变安全专业审查由 Ringo 把关的长期规则。

