# 账单读取安全意见与验证记录（2026-10-19）

来源：[Issue #137](https://github.com/DrErwin/hackerthon-bank-agent/issues/137)。业务依据为 [Erwin 10-18 临时口径](https://github.com/DrErwin/hackerthon-bank-agent/issues/137#issuecomment-6250123462)及公共契约 §4、§5.3。代码核对基线为 main `80acec31ec59df6bd07f97c8f29b982d684f6ad9`。

记录性质：Ringo 授权 AI 辅助复核与实施。下述意见及自动化验证分别留痕。2026-10-20 合并记录：Ringo 本人真人专业签核未取得；项目负责人 Erwin 决定在 v0.4 收口日合并本 PR，以项目负责人决定豁免替代真人签核并如实留痕（非 Ringo 本人审查，不冒充签核）。本文件不代表全系统安全测试通过。

## 1. 四项书面结论

| #137 条款 | 采用口径 | 放行边界与责任 |
|---|---|---|
| 1 读账风险 | 本人账户 L01 / B01 / B08 读取按 LOW、免确认及免验证 | 先由可信身份准入，再由银行逐账户核验归属；旧轮次、无有效会话及已终止任务维持拒绝。该分类来自既定读取政策，不是诈骗检测结果 |
| 2 bills.read | 账户级本人读取权限 | 不授予报表资源的通用访问权，不包含 F22 至 F24 的敏感明细导出，也不包含订阅解约或其他写操作；资源下载继续单独鉴权 |
| 3 私有声明冻结 | 两条私有工具的声明由安全目录保存预期值，逐项全等比较 | 账单模块保留实现及原声明，改动须新安全审阅；禁止由模块对象或新部署自动更新白名单 |
| 4 审计证据 | 参数摘要与受控结果引用，默认仅附成功/失败等必要事实 | 逐笔流水与原始账户余额不进入 audit_evidence；账单改动由周恩宇按 #145 完成，审计机制保持原归属 |

本次沿用已定业务规则。若要让本人普通查账增加 step-up、扩大 bills.read 或允许普通审计留存完整流水，均属于新业务或数据政策选择，应交 Erwin 决定后另行安全评审。

## 2. 冻结清单及变更要求

| 对象 | 权限 | 等级 | 副作用 | 确认 | 超时 | 重试 |
|---|---|---|---|---|---|---|
| bills.bank.list_accounts | bills.read | READ | false | none | 10000ms | read_only |
| bills.bank.list_transactions | bills.read | READ | false | none | 10000ms | read_only |
| bills.summarize（公开准入） | bills.read | READ | false | none | 10000ms | read_only |

两条私有工具分别使用 bills.reads.AccountsReadInput / AccountList 和 bills.reads.TransactionsReadInput / TransactionList，handler_ref 与工具名一致。公开能力沿用 BillSummarizeInput / SpendingSummary，处理器为 bills.summarize；details 模式的声明修订属于 [Issue #136 项 5](https://github.com/DrErwin/hackerthon-bank-agent/issues/136)，实施时须同步申请安全预期更新，避免静默放行或联调中断。

修改六项属性、输入输出引用或处理器引用均拒绝旧白名单。新增 bills 工具保持默认拒绝；转账原策略保持本票边界之外。安全门负责通用裁决，登录时效与任务归属仍由平台核验，账户归属继续只由银行作为事实来源。仅凭 bills.read 和一个资源编号不能取得他人数据。

## 3. 审计整改的可验收口径

- tool.started 的业务证据使用 parameters_sha256；原始 account_id、查询区间等参数不整包复制到审计证据。
- tool.finished 保留 result_ref 及必要的状态或条数。引用必须沿现有用户、任务和轮次范围读取，不得通过审计自动展开为完整银行响应。结果未另行受控保存时，如实说明引用用途，不能声称可还原原始流水。
- 原始 counterparty_name、逐笔 amount_fen、summary、transaction_id 及 available_balance_fen 排除出读路径审计证据，通用手机号和账号脱敏不足以证明这些字段安全。业务页面按冻结契约展示的必要信息保持原规则。
- 失败只记规范错误码，原始上游文本与验证码等秘密保持禁止入日志。审计读取沿独立管理权限，普通用户或模型无法借审计入口读取他人资源；读取和回放不得触发业务执行。

主线 [reads.py:96](https://github.com/DrErwin/hackerthon-bank-agent/blob/80acec31ec59df6bd07f97c8f29b982d684f6ad9/backend/app/modules/bills/reads.py#L96)记录原始 parameters，[reads.py:110](https://github.com/DrErwin/hackerthon-bank-agent/blob/80acec31ec59df6bd07f97c8f29b982d684f6ad9/backend/app/modules/bills/reads.py#L110)的脱敏注释与实际结果不符。使用现有离线账单组合执行一次查询，11 份审计快照中，上述五类字段均可检出。探针仅输出字段存在性，不输出资料原文。

整改由 [Issue #145](https://github.com/DrErwin/hackerthon-bank-agent/issues/145)承接，避免重复建单。本安全 PR 不修改 bills/ 或 audit/，也不把已知缺口记为修复。现有落盘记录的处置还需 Erwin 盘点访问范围并决定清理或迁移方案，本轮保留原始证据，未改删历史数据库。按 PM 当前决定，#145 不阻塞平台票 05 阶段一，但仍须在版本验收保留缺口。

## 4. 验证与限制

新增 test_bills_read_policy.py 共 43 项，覆盖字段漂移、业务对象原地修改及越权等分支。修复前，五项针对产品缺口的断言为红；首轮另有一项测试密钥长度准备错误，已修正。修复后与原策略测试组合为 57 passed。真实安全门和独立模拟银行记录核对：本人账户读到账单；他人账户与不存在账户的拒绝发生在读取处理器内，由银行按可信身份裁决并返回同一 ACCESS_DENIED（银行读取调用确实发生；只有用户、轮次、已终止任务三类拒绝发生在处理器之前）；两类拒绝均零资金写入，资金表及账本前后相同。

安全目录、账单集成及本机 HTTP 组合为 114 passed；完整后端离线回归为 659 passed（390.24 秒）。最终 head `69f6c5e` 复核：安全目录 100 passed（2026-10-20 实跑；43 项新增与 57 项定向均含在内）；全后端由 CI 的 backend pytest 覆盖，check 记录见本 PR。HTTP 使用受控模型替身。Python 编译检查通过，仓库未配置独立静态类型检查器。code-review 的 Standards 与 Spec 两轴独立复核均为 0 项发现，分别独立复跑 43 项及 57 项通过；此为 AI 检查，真人批准另记。随后同步 main c20553e 的订阅契约增量，安全与账单实现未变，契约及策略组合复验结果在 PR 记录。

本轮未调用付费模型，未做真实页面走查，也未扩充 122 / 274 / 330 的正式安全评测分母。#86、#88 的相关工作按 10-19 最新 PM 决定留在 v0.4，检测器及评测实施另票推进；33 轮 gated 在获得实际证据前保持 Blocked。
