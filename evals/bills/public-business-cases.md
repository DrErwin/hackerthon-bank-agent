# 票 06 第一阶段：L01 公共业务运行用例

负责人：周恩宇（Ethan）。范围：`evals/bills/`。本阶段交付17个实际公共业务运行场景（原14个加3个明确缺口），覆盖已合入主线的 L01；票 06 整体保持部分完成，不把尚未就绪的 L02/L03/导出/联调依赖算作通过。

依据：[票06](../../.scratch/v04-ethan-bills-backend/issues/06-full-business-eval.md)、[BF01—BF07](../../.scratch/v04-bills/spec.md)、[冻结公共契约](../../docs/contracts/公共契约-2026-09-23.md)、[账单PRD](../../docs/prd/02-账单分析-PRD-2026-09-23.md)、[评测指南](../README.md)。

## 真实路径与测试替身

每个场景建立独立的虚构 SQLite 银行与应用库；时间固定为北京时间2026-10-14 13:00。通过已注册 `bills.summarize` 的 Harness 调用 Entry/Service、真实 SecurityGate/执行器和 BankGateway/B01/B08。复用 `backend/app/modules/bills/test_public_integration.py` 中 Environment 的接线，不调用其测试函数，也不只调用私有算术内核。金额断言由实际银行流水按性质和方向独立求和；餐饮明细逐字段对照银行事实，退款额外回查原单。每个场景均核对余额、银行数据库全部表的摘要及资金提交次数不变。

Planner 固定选择 L01，scope_authorizer 与 LOW 风险判定是明确的测试策略；BILL-PUBLIC-09/10/11/15 注入具名 CALL_TIMEOUT。权限样本仅证明业务对真实安全门拒绝的响应，不证明生产策略、攻击检测或专业审查。选项直接经过 Harness.resume；没有运行 HTTP/F10 请求服务或浏览器。恢复覆盖真实持久化和新 Entry/会话，不冒称操作系统进程崩溃恢复。

## 八字段运行样本表

以下编号是本阶段运行场景ID，链接既有设计时仅表示相关子断言。它们不作为17条全新设计与原96条相加。源代码准备完成后的实际归档结果统一由 [run-log.md](run-log-public-06.md) 和原始报告认定；本表不会把未运行填成Passed。

| 编号 | 业务维度 | 映射依据 | 前置环境与数据状态 | 用户指令/输入 | Agent 预期交互 | 预期结果与硬性断言 | 自动化映射 & 状态 |
|---|---|---|---|---|---|---|---|
| BILL-PUBLIC-01 | 全部本人账户汇总 | BF01；公共契约 §5.3 / M05；既有设计子断言 BILL-001 | U1/D1 有效会话；2026-10-14 固定银行时钟；A1/A5 完整 9 月种子流水 | 2026年9月所有账户账单 | 注册 L01 经 Harness 查询两个本人账户 | 18 条实际 B08 流水；gross=586400/refund=4500/net=581900 分；逐笔独立复算；七类与 source_as_of 完整；真实安全门允许 | `test_public_business_case[BILL-PUBLIC-01]`；已实现，归档结果见[运行台账](run-log-public-06.md) |
| BILL-PUBLIC-02 | 账户缺失后选单账户 | BF01 / BF05；公共契约 §5.3 BillScope；BF05 | 有效会话，两个本人账户；用户未指定账户 | 2026年9月账单 | 先展示真实 B01 账户选项，选择主账户后沿原任务继续 | 选择前无 B08；成功范围仅被选账户；每笔实际 B08 读取均为该账户；金额与该账户银行事实一致 | `test_public_business_case[BILL-PUBLIC-02]`；已实现，归档结果见[运行台账](run-log-public-06.md) |
| BILL-PUBLIC-03 | 缺月份澄清与逐项补齐 | BF05 / BF06；PRD SOP-1；公共契约 §5.3；BF05/BF06；既有设计子断言 BILL-002 | 有效会话；未确认月份和账户 | 查账单 | 先等月份，选上月，再选所有本人账户；每次 resume 由真实 checkpoint 重建 Entry | 月份选择前零银行读取；最终 T1/R3；9 月完整范围和金额与真实 B08 一致 | `test_public_business_case[BILL-PUBLIC-03]`；已实现，归档结果见[运行台账](run-log-public-06.md) |
| BILL-PUBLIC-04 | 餐饮明细与原退款信息 | BF01；公共契约 §5.3 BillDetails / M16；§5.9 M11；既有设计子断言 BILL-STAT-17, BILL-STAT-25, BILL-018 | 9 月有两笔餐饮消费和一笔关联 8 月原单的退款；部分渠道为 null | 2026年9月所有账户餐饮明细 | 真实 L01 details 直接返回可查看明细 | 三条有序银行事实逐字段相等；退款类别复查原单；未知渠道保持 null；不创建报告或验证；不声称已验专业脱敏 | `test_public_business_case[BILL-PUBLIC-04]`；已实现，归档结果见[运行台账](run-log-public-06.md) |
| BILL-PUBLIC-05 | 退款/转账/利息分离与排除转账 | BF01 / BF05；公共契约 §5.3 / M05；§5.9 M11；票 08 否定词返修；既有设计子断言 BILL-001, BILL-004 | 9 月含退款、转入、利息；7 月额外有真实 50000 分转出 | 2026年9月所有账户不含转账消费统计 | 查询 9 月消费口径，再以独立 T2 查询 7 月同一否定口径 | 消费 gross-refund=net，不混转账/利息；7 月 transfer_out=50000 单列；不把不含转账误答成转账支出；两次任务仍计一个运行场景 | `test_public_business_case[BILL-PUBLIC-05]`；已实现，归档结果见[运行台账](run-log-public-06.md) |
| BILL-PUBLIC-06 | 完整空月与零额 | BF01；公共契约 §2.2 / §5.3；既有设计子断言 BILL-003 | 银行允许 2024 年 11 月范围，种子完整返回空集 | 2024年11月所有账户账单 | 实际 B08 成功完整读取后说明没有记录 | succeeded、transaction_count=0；金额为零、所有 share_bps=null；真实调用存在；消息明确没有记录 | `test_public_business_case[BILL-PUBLIC-06]`；已实现，归档结果见[运行台账](run-log-public-06.md) |
| BILL-PUBLIC-07 | 银行拒绝不支持的历史范围 | BF01 / BF06；公共契约 §2.2 / §5.3；既有设计子断言 BILL-020 | 银行仍按自己的最近 24 个月规则判断范围 | 2020年1月所有账户账单 | 保留用户原 2020 年范围交给真实银行，再返回明确拒绝 | failed、data=null、code/upstream_code=RANGE_UNSUPPORTED；所有尝试仍是 2020 年，未缩短后伪装成功；不计最小越界边界已测 | `test_public_business_case[BILL-PUBLIC-07]`；已实现，归档结果见[运行台账](run-log-public-06.md) |
| BILL-PUBLIC-08 | 真实安全门对拒绝裁决的业务响应 | BF01 / BF06；公共契约 §5.3 登录读取；账单只读权限边界 | 有效会话，但本样本 scripted scope_authorizer 返回不允许 | 2026年9月所有账户账单 | 真实 SecurityGate 在 BankGateway 前拒绝 | failed、source=security、data=null；bank reads=0；真实 block 决策；仅证明业务响应，不代替攻击检测或生产策略审查 | `test_public_business_case[BILL-PUBLIC-08]`；已实现，归档结果见[运行台账](run-log-public-06.md) |
| BILL-PUBLIC-09 | B01 失败后原任务重试 | BF06；公共契约 §5.3；BF06；既有设计子断言 BILL-006, BILL-FLOW-02 | list_accounts 首轮注入 CALL_TIMEOUT，恢复后调用真实银行 | 2026年9月所有账户账单 | 等待重新查询原范围，点击后继续 T1 | 首轮 waiting_input/data=null 且无 B08；恢复真实 B01/B08 后 T1/R2 succeeded，金额与银行事实相等 | `test_public_business_case[BILL-PUBLIC-09]`；已实现，归档结果见[运行台账](run-log-public-06.md) |
| BILL-PUBLIC-10 | B08 失败后原任务重试 | BF06；公共契约 §5.3 / M05；BF06；既有设计子断言 BILL-006, BILL-STAT-22, BILL-FLOW-02 | 真实 B01 可用；list_transactions 首轮注入 CALL_TIMEOUT | 2026年9月所有账户账单 | 失败等待；恢复真实 B08 后只读重试原范围 | 首轮 waiting_input/data=null；恢复后 T1/R2 succeeded，完整金额由真实银行逐笔复算；不冒称超时检测器通过 | `test_public_business_case[BILL-PUBLIC-10]`；已实现，归档结果见[运行台账](run-log-public-06.md) |
| BILL-PUBLIC-11 | 多账户部分成功不伪装完整 | BF01 / BF06；公共契约 §5.3 / M05；既有设计子断言 BILL-STAT-15 | A1 使用真实 B08 成功，A5 注入 CALL_TIMEOUT | 2026年9月所有账户账单 | 第一个账户成功后第二个失败，保持原任务等待重试 | 确有一次真实账户成功和一次注入失败；整体 waiting_input/data=null，不能把 A1 金额当全部账户；不跳过坏账户 | `test_public_business_case[BILL-PUBLIC-11]`；已实现，归档结果见[运行台账](run-log-public-06.md) |
| BILL-PUBLIC-12 | Harness 原请求幂等重放 | BF06；公共契约 §5.1 request_id；BF06 | 首次真实 L01 查询成功后，复用相同 request_id 与输入 | 2026年9月所有账户账单 | Harness 返回既有任务结果 | 两次 ModuleResult 相等，银行读取次数不增；这是 Harness 防重，不能替代票 09 的模块防重变异验证 | `test_public_business_case[BILL-PUBLIC-12]`；已实现，归档结果见[运行台账](run-log-public-06.md) |
| BILL-PUBLIC-13 | 取消后旧选项不复活任务 | BF05 / BF06；公共契约 §5.1；BF05/BF06；既有设计子断言 BILL-FLOW-03 | T1 尚在等待月份，保留旧选项 ID | 查账单 | 取消 T1 后再次回传旧月份选项 | 取消结果和旧选项重放均为 cancelled/data=null；始终零银行读取；不以宽泛捕获异常充当通过 | `test_public_business_case[BILL-PUBLIC-13]`；已实现，归档结果见[运行台账](run-log-public-06.md) |
| BILL-PUBLIC-14 | 同用户跨会话恢复 | BF05 / BF06；公共契约 §6.3；BF05/BF06；既有设计子断言 BILL-FLOW-01 | S1 的 T1 等待月份，同一 U1/D1 建立 S2 | 查账单 | recover_session 后确认继续，再选月份和账户，沿原任务真实查询 | 旧选项不复用，恢复时零银行读取；最终 T1/R5 成功且持久化 session_id=S2；不是断电/进程崩溃恢复证据 | `test_public_business_case[BILL-PUBLIC-14]`；已实现，归档结果见[运行台账](run-log-public-06.md) |
| BILL-PUBLIC-15 | 跨月退款原单补查失败与原任务重试 | BF01 / BF06；公共契约 §5.3 完整性；§5.9 M11；既有设计子断言 BILL-STAT-25, BILL-FLOW-02 | 两个账户9月主范围真实B08均成功；仅补查关联8月原退款单的窄范围注入CALL_TIMEOUT | 2026年9月所有账户账单 | 缺原单依据时等待重新查询原范围；恢复银行后沿同一T1继续 | 主范围成功不掩盖原单缺失；首轮waiting_input/data=null；重试T1/R2成功，18条本期记录，gross/refund/net=586400/4500/581900分；原单不重计入9月 | `test_public_business_case[BILL-PUBLIC-15]`；已实现，归档结果见[运行台账](run-log-public-06.md) |
| BILL-PUBLIC-16 | 非空账户范围的类别无匹配明细 | BF01 / BF05；公共契约 §5.3 BillDetails / M16；既有设计子断言 BILL-STAT-17 | 储蓄账户A5的9月银行流水非空，含医疗/居住消费，没有餐饮匹配 | 2026年9月餐饮明细 | 先展示真实账户选项，用户选A5后完整取数并筛选餐饮 | 选择前无B08，选择后只读A5；原范围确有流水但BillDetails.transactions为空；scope/source_as_of完整且消息说明没有匹配记录 | `test_public_business_case[BILL-PUBLIC-16]`；已实现，归档结果见[运行台账](run-log-public-06.md) |
| BILL-PUBLIC-17 | 排除普通类别先澄清再明确改口径 | BF01 / BF05；BF05；票08否定口径返修；公共契约 §5.3 | 用户明确排除餐饮，现有L01对话不支持任意类别减除；完整9月银行种子可用 | 2026年9月所有账户不含餐饮账单 | 任何银行读取前先等用户选查看全部类别，确认新口径后沿原T1继续 | 首轮waiting_input/data=null且零银行读取；仅显式选择后T1/R2成功；最终餐饮仍有实际支出，完整18条/净581900分，不静默扩大范围 | `test_public_business_case[BILL-PUBLIC-17]`；已实现，归档结果见[运行台账](run-log-public-06.md) |

## 覆盖与仍缺的工作

| 功能/规则 | 本阶段执行编号 | 尚不能认定完成的分支 |
|---|---|---|
| L01汇总与来源 | 01、02、05、06、07、11、15 | 非正净额、结构化比较、最小24个月端点、重复/空账户、更多完整性错误的公共样本 |
| L01明细 | 04、16 | 目前有餐饮非空与无匹配两个场景；其他类别、错误原退款关联与详情权限变体需要继续补齐 |
| 范围与账户澄清 | 02、03、17 | 复杂时间、纠正范围后的旧数据失效，不能仅靠同义改写补数量 |
| 失败/拒绝/恢复 | 08—15 | 各错误类型仍未达到每类≥3；断进程重启另测；跨用户/过期会话不是本轮权限样本 |
| 同期算术报告 | 另见历史147项及50项专项 | 147=130算术+17工具；50与147重叠；同一设计的不同层证据不累计成独立覆盖 |

17个 L01 公共场景包含原14个，不能相加为31个。该规模不代表“每个子功能≥10、每类异常≥3且消除全部缺口”的完整票06验收。上述L01缺项是待补用例，不借外部依赖标为Blocked。

## 逐路径依赖：Blocked独立报告

| 路径 | BF | 状态 | 提供方/依赖 | 当前受测版本的阻塞依据 |
|---|---|---|---|---|
| L02 locate/single/scan | BF02,BF05,BF06 | Blocked | Ethan / Erwin integration；ticket 04 | L02 is not registered in this tested main-based source revision; its independent development branch is outside this run. |
| L03 generate_report | BF03 | Blocked | Ethan / Erwin integration；ticket 05 | L03 BillReport business code is merged in this tested source; production capability registration and safety approval are not part of this L01-only evaluation. |
| F21 report resource and F22-F24 ordinary card export | BF04 | Blocked | Erwin / Ethan integration；ticket 05 / Issue 123 | F21/F22-F24 platform endpoints exist, but the present L01-only test does not invoke or verify report-resource and export HTTP paths; these have separate ticket 07 tests. |
| F22-F24 sensitive detail export and verification | BF04 | Blocked | Erwin / Ringo / Ethan integration；ticket 05 / shared verification-export wiring | Needs trusted public verification/resource integration; this scope-authorizer test policy cannot sign off sensitive export. |
| live planner/provider over HTTP | BF01,BF05,BF06 | Blocked | Erwin / Ethan integration；ticket 07 / real provider and HTTP runtime | This runner supplies a scripted planner and no live provider configuration or running HTTP service; no real-model/HTTP evidence is available. |
| React bills UI and browser workflow | BF07 | Blocked | frontend owner / Ethan integration；ticket 07 / integrated frontend and backend | Requires the actual UI/runtime joint environment; no browser or page execution occurs here. |
| professional attack detection and production policy review | BF01,BF02,BF04 | Blocked | Ringo；professional security review | Business reactions to test policy are measured separately; no professional detector or production-policy approval is inferred. |

这些路径不送入pytest形成skip/xfailed，也不作为“通过的业务样本”。依赖状态以原始报告固定的源码版本和运行环境为准；后续分支合入后逐路径增加实跑证据。

## 归档与复现

```bash
python -m pytest -q evals/bills/
python evals/bills/run_business_evidence.py --revision <已发布的40位源码提交SHA>
```

先提交并发布受测源码，再以该实际可取得的提交执行runner；证据提交追加在源码之后。运行器正向校验完整后端/种子/公共契约/helper及真实包初始化器的Git对象，核验运行时 app 模块文件路径，并在执行前后再次检查源码。输出 `evidence/<北京时间日期>/*-public-l01-phase1-<SHA前12位>.json.gz`，以独占创建防止覆盖。run-log登记解压JSON SHA256、提交、时间、分层数量和命令；原始JSON中的sample包含实际task/run/request/session、状态、金额、调用与银行库不变证据。

`phase_result=Passed` 只表示已执行样本符合预期（可包括正确拒绝、等待或取消）；`overall_status=partial` 与逐路径Blocked共同保留。已存在的算术原始报告不回写、不改hash、不移动历史时间。
