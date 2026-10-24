# 01：生日动作与限定收尾安全门

Ticket ID: v05-cross-security/01

Package: [v05-cross-linkage/packages/02-security：安全边界与专项核验](../../v05-cross-linkage/packages/02-security.md)

Spec: [本工作组规格](../spec.md)

Type: 开发

Owner: Erwin（v0.5 本阶段统一负责）

Directory: `backend/app/security/`

Status: in_review — 实现与本目录验证、转账/订阅安全回归已完成（2026-10-24），待 Erwin 本人安全审阅与 PR 审查合入。

Package accepted by: Erwin

Package accepted at: 2026-10-24

Execution assignee: ZCode 执行对话（Erwin 指派，2026-10-24）

Accepted by: 未记录（具体实施票）

Accepted at: 未记录

Planning approved by: PM，2026-10-24「认可，按此方案推进」。只批准规划/拆票，不代表本票实施或安全签核已获批准。

Core scenarios: XL-B05—B07、X05—X08；定义见[共享规格 §5](../../v05-cross-linkage/spec.md)及[E2E 设计](../../../evals/cross/representative-cases.md)。

## What to build

冻结/下单/核销按声明确认与验证；收尾只释放原冻结未消费部分。测试越权、篡改、过期、未知、必要审计失败；复用现有执行器

## Blocked by

- [v05-cross-platform/01：公共模型落地](../../v05-cross-platform/issues/01-public-models.md)

## Start when

- Erwin 已于 2026-10-24 明确领取包 02；本聊天获准拆票与交接，代码/实跑由后续明确指派的执行对话领取后开展。
- 前置票的公开能力与实际合入证据齐备，不以计划文档代替能力。已定契约下的局部假实现遵守仓库并行规则，不能作为真实接入完成。
- C6/C7 的资金和隐私规则由 Erwin 按本阶段授权本人审阅并记录结论；本次转派本身不算确认通过。

## Acceptance criteria

- [ ] 每种新动作的权限、副作用、确认、验证、审计规则明确，不能由模型填写放行结果。
- [ ] 冻结时限定授权绑定本人/任务/轮次/原冻结；取消或安全终止只能收尾，不批准购买。
- [ ] 存在未知在途先核对，已消费不退，零剩余不提交零金额释放；参数篡改、过期或越权拒绝。
- [ ] 必要审计或授权事实不可用时按原规则阻止敏感执行；确认及验证复用不扩大原授权范围。

## 实施交接：新动作与限定收尾

**输入**：服务端可信身份和父子关系、已登记工具声明、真实动作/参数版本、确认/验证引用、原冻结及在途资金事实、限定释放授权和结束原因。模型/用户普通文本不能提供“已放行”事实。

**输出**：复用公共 SecurityDecision 与交互类型；生日动作能按规则暂停/确认/验证/拒绝/执行；安全记录与授权可恢复，供平台 09 装配和业务 03 使用。执行放行不等于银行成功。

### 实施顺序

1. 对照现行契约 §3.5、§4 与安全附件，列出冻结/下单/核销/查询/限定释放的权限、确认、验证、审计和终止处理。保留原字段与状态语义；已有规则不重新让 PM 选择，新增差异/兼容影响交 Erwin 本人审阅并记录结论。
2. 复用已有注册、执行器和安全持久状态。落实被冻结用户确认授予的限定授权、冻结结果绑定及状态更新，支持重启回查；确认未批准、冻结失败或其他用户引用不能产生有效收尾权。
3. 新购买沿原每动作确认及验证；参数变更使旧批准失效。使用 D1/父子可信记录判断相关范围，不能把调用方自报的 parent_task_id 当作放行依据。
4. 专门支持“停止购买后的限定查询/释放”：可信身份核对原用户/任务/账户/轮次/冻结，先核实在途和银行未消费额，仅释放原余额。原冻结确认已含此授权，结束释放不再新弹一次确认；普通 resume 和其他工具仍受终止限制。
5. 将允许动作与参数/资源/操作编号及当前授权绑定，提供银行授权可核对的结果。必要审计或授权记录写入失败不放行；不提供任意编号通过或恒真授权回调。
6. 在本目录完成针对性验证和原转账/订阅安全回归，提供声明/接入说明、状态示例及证据。平台 09 负责实际 runtime/网关装配，cross 负责业务次序；本票不能直接修改这两个目录。

**须核对的现有接缝**：注册器对所有副作用要求 per_action，执行器对终止任务直接拒绝；限定释放必须保留明确的授权来源和受控执行路径，不能简单取消这两条限制。网关 authorize_birthday 只传身份/操作编号/动作名，如何核对已批准参数须有可审查说明和验证；接口不足时回提供方单目录补齐，列明依赖，不能扩展本票目录范围。

### 本票验证与交付标准

| 条件 | 必须看到的结果 |
|---|---|
| 正常冻结、下单、核销；拒绝或验证未通过 | 合法确认后才执行；未批准路径银行写入为 0 |
| 账户/商品/金额/订单/计划版本变化，旧按钮重放 | 旧批准不能用于新参数；重新核对并确认，归属错误拒绝 |
| 冻结成功但响应丢失；冻结明确失败 | 未知仅查原操作后绑定；失败授权无效，不生成新冻结补偿 |
| 500 冻结，花付款199后取消或安全终止 | 停新购，核实无在途后只释放301；不退款，不复活普通业务 |
| 会话失效、重启、旧轮次、跨用户/任务/账户冻结引用 | 合法受控收尾可恢复；一般业务仍须有效会话与权限；错误归属拒绝 |
| 未知核销、释放失败/未知、余额为0 | 在途不释放；未知查原释放编号；余额0无释放写入，不报未核实成功 |
| 重复点击、同号同参/异参 | 已成功写入不重复；冲突拒绝；原转账和订阅确认/验证行为保持 |
| 缺授权/事实、任务状态读取失败、必要审计失败 | 拒绝或暂停且零新增银行写入，保留可追溯原因 |

测试通过安全公开入口观察结果、审计关联与实际写入次数；允许在本目录测试中使用已有银行服务或受控替身，但分别标注，不写成页面 E2E。不得仅断言“返回 allow”却不验证错误参数无法执行。

**回交**：规则差异及 Erwin 本人结论、实现/测试/兼容结果、PR 与实际审查/合入记录、真实接口及使用样例、未满足的跨目录依赖。无需等页面和安全专项票 02 完成才交付安全能力；涉及尚缺公共类型/存储/网关接缝，先给出具体缺口与提供票，不在本目录复制公共结构。

## Verification

本票按下列可观察行为验证，报告基线、输入、实际结果与证据位置。局部验证不等于三主线 E2E 通过。

相关正常/关键分支、暂停恢复、权限拒绝和异常处理须有证据；验证只围绕本票影响范围展开。缺陷回所属实施目录修复。本票不得跨目录补代码；实际发现新公共缺口时更新依赖并交给提供方。

## Delivery record

- 实现 / PR / 合入：实现完成于分支 `feat/security/birthday-release-gates`（基线 `fedce40`，rebase 至 `2bfd687`，仅 `backend/app/security/`）：`state.py` 新增 `FreezeReleaseAuthorization` 记录与持久化（表 `security_release_authorizations`，只增不改既有方法）；新模块 `birthday_policy.py`（冻结工具声明、MEDIUM/LOW 风险规则、§3.5 条款）与 `birthday_release.py`（授权授予、冻结结果绑定、限定收尾执行器、`authorize_birthday_write` 银行回调）。[PR #272](https://github.com/DrErwin/hackerthon-bank-agent/pull/272)；CI 作业 0 步骤即失败，与 #268 相同的 GitHub 账户计费阻塞（非代码原因，已在 PR 留言并附本地等价验证）；合入状态以 PR 为准。
- 本票验证：2026-10-24，`backend/.venv`。新增 `test_birthday_release.py`（27 条：授予 5、绑定 5（含冻结响应丢失按原编号绑定激活）、收尾 17（含旧轮次拒绝、任务状态读取失败））与 `test_birthday_policy.py`（购买路径 11：确认→中风险双因子→执行、冻结/下单/核销三动作全链路真实银行写入、未批零写入、参数篡改 CONFIRMATION_STALE、终止后仅限定收尾等），41 passed（真实 MockBankService + BankGateway 层）。回归：`app/security/` 424 passed；转账/订阅/审计（transfer、subscription、agent_platform runtime、audit）184 passed；后端全量 1538 passed（修复前基线，修复后 security 目录复跑 424 passed）。
- AI 审查（子代理）：2026-10-24 完成一轮，结论"暂不可合入"：blocking 1（bind_freeze_result 不接受网关 get_operation 的 OperationFound 包装，冻结响应丢失后授权永远无法激活）+ major 2（end_reason 丢弃、收尾不核验当前轮次）+ minor 5。已全部修复：B-1 解包 OperationFound 并补"冻结响应丢失→finalize 回查绑定→释放恰一次"测试；M-1 end_reason 以 `end_reason:<原因>` 进入收尾裁决 evidence_refs（快照内关联由平台 09 装配，AuthorizationSnapshot 为冻结契约无该字段）；M-2 LimitedReleaseFinalizer 增加可选 `current_demo_round` 缝隙，记录轮次非当前轮即 STALE_ROUND 拒绝并附测试；minor：freeze_id 入 evidence_refs、下单/核销全链路测试、任务状态读取失败测试、删除未用参数；`claim_release_execution` 不自证授权有效（前置不变量在 finalizer，与 claim_execution 对确认的校验不对称）留作 Erwin 签核知悉项。
- AI 复审（子代理，提交 04545ec/43c4200）：**结论"可合入"**——B-1 两条链（finalize 回查链与 bind 直传链）经独立复现脚本与真实链路测试验证；M-1 表示法可接受；M-2 缝隙设计正确；minor 全落实；复审独立复跑 新增 41 passed、security 424×3、回归 392 passed。遗留非阻塞 R-1/R-2 已随本票处理（R-1 依赖登记补"finalize 必须传 current_demo_round"；R-2 测试装备默认超时调大、仅响应丢失用例收紧），R-3 为复审撞上 rebase 中间态、已随 43c4200 解决。合入前待 Erwin 本人安全签核（含规则差异 5 点、end_reason 表示法、claim_release_execution 知悉项）。
- 规则差异与决定：① `bank.release_frozen` 不注册为模型工具，模型发起的释放被 registered-tools-only 拒绝，仅受控收尾路径可释放；② 释放授权绑定 (user, session, round, task, account, freeze_operation_id, confirmation, max_amount)，状态机 pending_freeze→active/invalid、active→completed/invalid，篡改任何身份字段即 OPERATION_CONFLICT；③ 收尾前置：任务已结束（task_state_resolver=True）+ 本任务无 processing/unknown 在途 + B13 实时余额；余额 0 不提交零金额释放；余额超确认上限暂停不超额释放；④ 释放未知/失败仅沿原 operation_id 回查，不换号重做；⑤ 授权回调按（身份、操作编号、动作名、活跃 allow claim）绑定，参数绑定依赖银行同编号参数摘要与 claim 的 parameters_ref——回调不传参数是网关接口现状，如需回调级参数核对属网关/平台单目录补齐，已在模块 docstring 与 PR 说明登记。
- Erwin 本人安全审阅：2026-10-24 给出定向裁定（聊天原意）：以用户体验为出发点——办理信息尽量对用户可见；用户想完成的操作整个系统要有办法完成；AI 做自由裁量（选品、比价、改计划），动钱与否走确定性规则，风险处由用户确认授权。按此口径映射：规则差异 1-3 成立（钱=确定性判定+冻结确认单一次看清并授权+暂停态均有完成路径：结果不明可回查、先取消即可收尾、专用通道始终能释放），4 维持现状并登记为网关可选增强，5/6 认可，7 知悉。据"办理信息可见"要求同日补齐收尾回执三数（已消费/已释放/仍冻结，`ReleaseOutcome.consumed_total_fen` + 人话金额消息，security 424 passed）。合入决定待 Erwin。
- 联合 E2E：未因本票发布而通过；由[联动 E2E 包](../../v05-cross-linkage/packages/05-cross-e2e.md)统一关联。
- 真人安全签核 / PM 最终验收：未由本票代签。
- 跨目录依赖登记：无新增公共缺口；平台 09 装配时将 `authorize_birthday_write(state)` 接入 BankGateway、在冻结确认作答后调 `grant_release_authorization`、冻结结果后调 `bind_freeze_result`、任务结束时调 `LimitedReleaseFinalizer.finalize`——**finalize 装配时必须传 `current_demo_round`**（缝隙可选，缺省 None 时旧轮次防护不生效，复审 R-1）；网关 authorize_birthday 回调如需可见参数，回提供方单独补齐。

## Comments

2026-10-24：按 PM 已批准拆分发布，来源为[拆票方案候选 13](../../v05-cross-linkage/ticket-proposal.md)。票面 Owner 为目录归属，不表示其本人已领取。

2026-10-24（责任更新）：本票本阶段执行由 Erwin 承担；具体票的开工、实现和验证状态仍按实际结果记录。

2026-10-24（接包细化）：Erwin 已领取包 02，要求本聊天拆票、由其他对话执行。沿用原两票及目录/依赖，补齐输入输出、实施顺序、验证和回交；未记录具体执行者领取，未编码、未实跑。

2026-10-24（执行记录）：ZCode 执行对话按交接指派领取本票，基线 `fedce40`，独立 worktree/分支实现；规则差异、验证结果与跨目录依赖见 Delivery record。AI 审查由子代理另行执行，不冒充 Erwin 本人安全审阅。
