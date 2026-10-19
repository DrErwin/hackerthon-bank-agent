# mock_bank —— 模拟银行

归属：底座（Erwin）。

放什么：账户与账本、账户操作权限、交易规则、限额与风控、操作去重与结果查询；模拟身份验证（验证码 / 人脸，带演示开关）、预约转账到点执行、外部生活服务 Mock（价目表取数）、环境重置。

依据：[MockBank-PRD](../../../../docs/prd/MockBank-PRD-2026-09-23.md)（第 9 章能力表 = 业务模块找银行要能力的唯一入口；第 2 章种子八张表）。

边界：不理解自然语言，不与前端直连；银行自有数据在 `storage/mock_bank/` 的银行库，应用不跨边界直读写。

`MockBankService` 按银行库事实执行普通转账，使用固定演示账户、收款人和银行侧规则；启动时重复播种不会覆盖已有余额。给妈妈转 500 元使用 U1 的 A1 账户与 A2 收款人。B09 在提交时重新检查收款人、账户、余额、限额和风险；同号同参只读原结果，转账与账本同事务落地。银行慢操作先保存 `processing`，完成后在原编号下原子结算，供 B14 回查。

单进程演示服务若在慢操作写入 `processing` 后、账本结算前中断，下次启动会把原编号结案为明确失败（`STATE_CONFLICT`，原因 `processing_interrupted`）；这时余额和流水均未改变。同编号查询与重复提交只返回该失败结果，不会重新扣款。

验证挑战和提交结果保存在同一个银行 SQLite 文件中；验证码由启动时提供的至少 32 字节 `demo_secret` 和挑战编号生成，不落盘。重启时使用相同密钥，未完成挑战的演示码才保持有效；提交去重只保存带密钥的比较值。密钥由服务端受控配置提供，不进入日志、模型或银行库。验证码只供后端演示专用路径读取，不出现在普通核验返回。低风险会话验证与中风险动作验证分别按冻结契约处理；安全模块仍负责确认与动作参数、权限、会话有效性等最终执行判断。

本 PR 合入前若已有旧版演示银行库，其操作没有轮次归属且含明文模拟码；服务会明确拒绝加载。先保留旧库供核对，再由演示管理员显式启用新的银行库，不静默改写原操作或清除数据。

从 `backend/` 验证：`python -m pytest -q app/services/`。

## B08 流水查询与共用种子流水（v04-bills-bank-seam/02）

`list_transactions(user_id, account_id, start_at, end_at)` 按冻结附件 B08 返回一个账户在**半开区间**（含开始、不含结束）内的完整流水，不分页：非本人账户一律 `ACCESS_DENIED`；`start_at >= end_at`、时间无时区或账户编号为空返回 `INVALID_ARGUMENT`；起点早于银行时钟往前 24 个月返回 `RANGE_UNSUPPORTED`，details 用冻结键名 `earliest_supported_at`（只约束起点：账单问「本月」会给出未来的月末，终点晚于当前时刻不算越界）；范围判定与 `as_of` 都取银行自己的时钟（`MockBankService(..., clock=...)` 可注入，默认真实时钟），不看调用方时间；无数据是成功的空列表，与任何失败严格区分；返回行按发生时间再按 `account_id` / `transaction_id` 稳定排序。

事实来源：账本事实列（票 03）直接给出对手方、渠道、摘要与退款原单；**本次会话里发生的转账**写入时还没有这些列，银行按自己的操作回执补全（收款人脱敏名与账号；本人账户互转的入账腿取付款账户的银行侧名称；回执不含渠道，故渠道如实为 null，摘要「转账」是该行自身的动作名称）。任何一行拿不到必需事实（例如退款缺原消费、时间不可解析）时整个查询以冻结错误码 `BANK_UNAVAILABLE` 失败——不丢行、不编造、不把残缺结果当完整成功。

`seed_flow_history()` 载入 `seeds/flow_history.json`（另含订阅线的 `seeds/subscription_flows.json`，见下节）：按银行时钟把「相对月份 + 日 + 时刻」落成绝对时间，**不生成晚于银行时钟的样本**（当天还没到的时刻会被跳过，不会出现「未来流水」）；`transaction_id` 含实际日期，因此**同一时刻重复调用幂等**（按 `transaction_id` 去重），换月后同一 `ref` 会落成新一个月的样本、逐月累积；种子行的 `operation_id` 以 `seed:` 标明不是真实操作。样本覆盖 12 个月（A1：消费七类、一笔未知渠道消费、跨月退款、活期利息、家电大额消费）与 6 个月（A5：转入、门诊、水费、利息）；**转账流出样本不落在「今天」**，避免吃掉演示的当日转账额度（`get_limits` 只计流出转账）。默认不播种，本机演示的启用见票 04。

## 签约代扣 B29/B30 与订阅种子（v04-subscription/02）

`list_subscriptions(user_id, account_id=None, status=None)`（B29）返回本人签约代扣协议：空 `user_id`、空/非字符串的 `account_id`、非法 `status` 返回 `INVALID_ARGUMENT`，非本人或不存在的账户一律 `ACCESS_DENIED`（不区分「不存在」与「不属于本人」），按 `mandate_id` 排序，`as_of` 取银行时钟。`cancel_subscription(context, operation_id, mandate_id)`（B30）只允许解约本人名下 `status="active"`、`next_billing_at` 非空且绑定账户 `status="active"` 的协议：缺失或非 UUID4 的 `operation_id`、空或非字符串的 `mandate_id`、跨用户、不存在、已解约、无下一期、账户冻结分别返回 `INVALID_ARGUMENT` / `ACCESS_DENIED` / `RECORD_NOT_FOUND` / `STATE_CONFLICT`（`reason` 为 `mandate_already_cancelled` 或 `mandate_without_next_billing`）/ `ACCOUNT_UNAVAILABLE`；作用域记进既有的 `bank_operation_scopes`。

**B30 的编号与生效条件（按 2026-10-19 审查意见收紧）**：编号在**动账之前**先绑定首次参数（`bank_subscription_requests`，与作用域同一次判断），此后同编号同参数可安全重试、同编号换 `mandate_id`（包括被拒请求用过的编号）一律 `OPERATION_CONFLICT`；已落库的操作记录按编号幂等重放，返回首次 `OperationResult<SubscriptionCancelReceipt>`。成功时先落协议行（`status="cancelled"`、`next_billing_at=NULL`、`cancelled_at`、`cancel_operation_id`），再写 `bank_operations`（`action_name="bank.cancel_subscription"`），B14 按编号还原同一回执；**若第二段写被拒（编号被别的动作占用、或银行库故障），本次调用按解约前快照回滚自己刚改的那一行**（`WHERE mandate_id=? AND cancel_operation_id=?`，不覆盖别人的解约），因此「没有回执就没有状态变化」，重放同一编号会重新走一次正常流程而不是 `STATE_CONFLICT`。并发同编号同参数只落一条操作记录、两边拿到同一回执。**已知根因未修**：协议行与操作记录仍是两次相邻事务，真正合一需要 `storage/` 暴露共享事务入口（不在本票写权限内），登记为后续票。


协议表 `bank_subscriptions` 由 `mock_bank/subscriptions.py` 自包含建表，落在同一个银行库里，`storage/` 不需要知道它的存在。签约种子 `seeds/subscriptions.json` 用相对偏移（`next_billing_day_offset` / `last_billed_month_offset` / `signed_month_offset` / `cancelled_month_offset`）在银行 `clock()` 上解析，扣款时刻固定为 09:00；`sub_001` 优酷 2500/月 active、`sub_002` 云端网盘 3900/月 active、`sub_003` 喜马拉雅 1500/月 cancelled（已解约对照项；票据只要求三家商户的订阅流水，故不新增该商户流水）。签约事实与演示账户一样默认播种，重复调用幂等（`INSERT OR IGNORE`，不覆盖运行期已解约的行，重启后解约状态保留）。

订阅扣款流水单独放在 `seeds/subscription_flows.json`（优酷近 6 个月、云端网盘近 3 个月、绿洲健身近 5 个月无签约 → 供疑似周期扣款识别）。**默认构造的银行只有签约、没有扣款流水**：订阅流水与共享流水一样，随显式入口 `seed_flow_history()` 一起幂等落库（同一时刻重复调用不增量；不带 `day` 的行按「银行时钟当月同日」解析，因此「连续 N 个自然月」的故事在任何演示日期都成立）。流水默认不播种的既有约定不变，隔离的单测银行库不会多出账本行；本机演示（`agent_platform/local_demo.py` 已调用该入口）自动获得订阅流水。

从 `backend/` 验证订阅能力：`python -m pytest -q app/services/test_subscriptions.py app/services/`。

## JSON 种子与转账评测数据（v03-transfer-evals/02）

账户初始余额、状态和展示信息来自 `seeds/accounts.json`，联系人资料来自 `seeds/payees.json`；完整号码是虚构测试资料，银行返回仍仅展示脱敏信息。两份文件按服务代码所在路径读取，不依赖启动目录。缺失文件或非法 JSON 会直接报错，不回退到硬编码数据。本工程当前采用源码 / editable 安装运行；普通 wheel 分发如需使用这些资源，须另行在构建配置中纳入 JSON（构建配置不在本票目录范围）。

默认仍播种 A1、A5、U2A1，余额与既有演示一致。新联系人 A8/A9 是不同银行的张伟（尾号1111/2222），A10/A11 是同银行的李明（3333/4444），A12 是无备注的赵强（手机号13812345678、19位虚构卡号）；其余新联系人使用16位虚构卡号。保留 A2/A3/A4/A7 的原资料与银行规则。

02 交付 D1 联系人和 D2 的 A6 / A8_ACC。03 建立隔离临时银行库后调用 `bank.seed_demo(include_evaluation=True)`，加入 A6（U1，active，50000分可用余额）及 A8_ACC（U1，frozen）。`seed_account` 只插入尚不存在的账户；重复播种或同库重启不会补回已扣余额，不清除流水，也不覆盖已有账户状态。已加入的评测账户在同库重启后继续保留，因此不要对开发者演示库调用此入口。

类别、closed 状态、历史日/年额度和故障注入仍由03准备；本票没有交付151条转账场景的自动化或真实模型评测。账户/联系人加载表保持既有测试接缝 `ACCOUNT_LABELS` / `PAYEES`，数据内容仅在 JSON 定义，限额与涉诈规则继续由银行代码裁决。

验证：从 `backend/` 运行 `python -m pytest -q app/services/test_seeds.py app/services/test_bank.py app/services/test_verification.py`，以及后端全量测试与 `../evals/mockbank/test_mockbank_eval.py`。新测试覆盖同名多候选、号码检索/手工核对、用户隔离、输出脱敏、一分钱不足、余额归零、冻结拒绝和重复播种/重启不重置账本。
