# 04：L02交易定位与四类异常规则

Ticket ID: v04-ethan-bills-backend/04
Type: 开发
Owner: 周恩宇
Directory: backend/app/modules/bills/
Status: resolved（L02 业务模块 #183 已合入；生产注册 #190、安全准入 #187/业务测试联动 #188 单列其它工作线）
Package: [v04-bills/01](../../v04-bills/packages/01-bills-backend.md)
Spec: [本人规格](../spec.md)
Core scenarios: [BF02/BF05/BF06](../../v04-bills/spec.md)
Blocked by: None（仅业务模块范围）；L02 默认真实运行时尚依赖平台 Issue #190/PR #192、安全 #187/PR #196、本人联动回归 #188/PR #197，未完成前不称已部署。
Verification: locate候选不代选；single核对银行事实；scan仅规则4；OR条件分开、基线不足、亲属例外、夜间端点、月末/锚点/日期容差；不代冻结/取消。

## 验收

只按PRD与§5.3/§5.9，RuleCheck区分evaluated与insufficient_data；不把attention当安全执行器risk。06:00恰好端点先由Erwin明确，不能猜答案后写通过。

## Comments

### 2026-10-19：L02 首轮实现与复核（前序基线历史）

- 基于首轮主线 `9741053c304a194a4c3d5ab3048f4dbb8be3b0f9` 的首轮提交 `9dfa61e`，11 个改动文件均在 `backend/app/modules/bills/`。实现 typed locate/single/scan、原任务候选选择与重读、四类私有规则、独立 `ANOMALY_MANIFEST` / `register_bills_anomalies` 以及模块和真实平台接缝测试。
- 模型直接引用公共 `DetectAnomaliesInput`、`TransactionCandidates`、`AnomalyResult`；L02 独立 factory 复用受控 B01/B08，不修改 L01 `CapabilityDefinition`、私有读取声明或安全目录。正式公共 L02 声明仍需安全线登记，当前未自行放行。
- 单笔核对来自重新读取的银行交易；不从用户或模型金额、亲属文字、候选展示值推断事实。银行范围限制按其 `RANGE_UNSUPPORTED.earliest_supported_at` 最多重试一次，不复制 24 个月保留规则。单独 ID 无法稳定定位时明确要求先按月份定位。
- 06:00 端点按 [Issue #132](https://github.com/DrErwin/hackerthon-bank-agent/issues/132) 的后续 PM 决定落实为北京时间 **[22:00, 06:00)**，恰好 06:00 为 evaluated/not_matched；此前票内“先明确”保留为原验收条件。真实亲属资料缺失时规则1为 insufficient_data，业务 attention 不代表安全执行器 risk。
- 首轮作者定向 **78 passed**。独立 Standards 复核另在 backend 执行 `python -m pytest -q app/modules/bills/test_anomaly_entry.py app/modules/bills/test_anomaly_service.py`：**54 passed in 1.81s**，与上述 78 项重叠。四项接缝测试使用真实 Harness、scoped SQLite、SecurityGate、执行器、BankGateway 和种子 Mock Bank；规划器与 LOW 风险策略仍是测试替身，F10 helper 未走 HTTP。
- 独立 Standards 主边界未见越权实现或应阻断的结构问题，但跨轴复现：上半月、下半月、多月份和具体日被静默改成整月取数，4 个请求实际返回 succeeded。另有引号内字段字面值及类型化重放问题待修。旧测试全绿没有覆盖这些缺口，不能作为整体审查通过。
- 作者随后基于 PR #153 合入后的新主线 `cd7c91ad80652852bb10fef139c2442d756ef359` 修复并重跑，结果见下一节。上游 journal 两文件随 rebase 继承，不计为本票越界改动。保持 `in_progress`；平台、真实模型/HTTP/页面和专业安全验收分开记录。

### 2026-10-19 后续：新主线修复与最终 Standards 复核

- 最终本地提交 `2843f6ba8d13cd4ce3a29bd340150398753691ac`，基线 `cd7c91ad80652852bb10fef139c2442d756ef359`；相对该基线仍只有 11 个 bills 文件。作者全 bills **253 passed**，其中 L02 定向 **94 passed**；本分支完整后端及最终远端见本节发布记录。
- 日期在读取前澄清，不支持的半月、具体日和第二月份不再变成单月。独立复核原“上半月、下半月、9 月和 10 月、9 月 15 日”四个请求，均为 `waiting_input` 且零银行调用。
- 先剥离商户/渠道引号内字面值，再解析模式、期间及所有账户；字面值不能提供其他字段的指令。保存结果重放恢复为真实 `TransactionCandidates` / `AnomalyResult`，沿用数据、ID 和交互，不重新读取或写 checkpoint。
- 三项 Spec 修复：规则2按全部既往交易识别已知对手方，规则1金额基线继续只用支出；缺少商户 ID 的消费使规则4为 insufficient_data，已有真实匹配证据仍可返回；完整银行查询确无该 ID 为 `RECORD_NOT_FOUND`，银行边界无法完整查询仍为 `BILLS_LOCATE_REQUIRED`。
- 独立复核执行 `python -m pytest -q app/modules/bills/test_anomaly_entry.py app/modules/bills/test_anomaly_service.py -k 'partial_days or merchant_literal or direct_replay or prior_inflow or missing_merchant_identity or single_unknown_id'`，**15 passed, 52 deselected in 2.01s**。Standards 本轴无新增硬性或结构阻断项；生产声明、权限装配和联合业务验收仍按各工作线执行，不因模块修复完成而关闭本票。
- 最终远端 [ad627f00e4d3ff94d54c612eac4d4499094c0769](https://github.com/DrErwin/hackerthon-bank-agent/commit/ad627f00e4d3ff94d54c612eac4d4499094c0769) 已推送，与完整受测 2843f6ba8d13cd4ce3a29bd340150398753691ac 的 Git 树均为 `129f9da59469fb9ad67de65bae0ae4fbd0f6223f`，已核对相等。本分支后端实际 **793 passed in 124.91s**；独立 Spec / Standards 两轴已完成复核。保持 `in_progress`，分支已发布不等于已经合入。

### 2026-10-20 收口日：模块已合入 + L02 接真实链路决定

- 独立审查（AI、非真人，钉 head `7d9682a`）为「有条件可合」：P0=0、P1=2（`ZoneInfo` 未声明 `tzdata` 导致 Windows 无法收集、分支落后 main 20 个提交）、P2=14；`single` 规则 4 命中为唯一存活变异（真实测试缺口）。合入前两项 P1 与 P2-1/2/10/14 一并处理后，[PR #183](https://github.com/DrErwin/hackerthon-bank-agent/pull/183) squash **`7a8dd1e`** 合入 main；合并后在 main 上 `app/modules/bills` **316 passed**、后端全量 948 passed、mockbank 14 passed、CI 绿。审查与修复为 AI 代行（PM 授权），非作者真人复核。
- **PM 2026-10-20 13:00 决定：L02 也接真实链路**。模块本身已完成；剩余两步在别的目录，不归本票：① 平台装配注册（`backend/app/agent_platform/local_demo.py` 调 `register_bills_anomalies`）；② 安全白名单（`backend/app/security/demo_policy.py` 按 #149/#164 口径写独立冻结快照，`policy_version` 再升位）。**两步未做前 L02 不进 `public_catalog()`、安全门仍拒绝，不得记作已可用。** 平台/安全侧实施与验收另记。

### 2026-10-20 晚 最新合入结论

[PR #183](https://github.com/DrErwin/hackerthon-bank-agent/pull/183) 已于 2026-10-20 squash 合入 main，Erwin 审查记录 L02 模块测试 316 passed / 后端 948 passed / MockBank 14 passed。**本票 L02 代码与模块级可复核测试交付完成**。默认运行时 `public_catalog` 仍依赖 Erwin 的 #190/PR #192，安全 `read-3` 白名单依赖 Ringo #187/PR #196，业务预期联动 #188 由 [PR #197](https://github.com/DrErwin/hackerthon-bank-agent/pull/197) 跟进；这些是跨线验收，不由本票越权修改。
