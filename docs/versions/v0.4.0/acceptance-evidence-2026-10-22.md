# v0.4 联合验收记录：BF01—BF07 与版本验收标准（2026-10-22）

> 对应交付包：[v04-bills/02 联合验收与收口](../../../.scratch/v04-bills/packages/02-v04-acceptance.md)。
> 口径：PM Erwin 2026-10-22 决定**不硬凑指标**——按现有实跑证据收口，缺口如实登记为[例外](#七例外清单)，**不写"全部通过"**；本记录由 AI 按 PM 授权代行整理与审查，**非 Ringo 真人安全签核**。v0.4 正式收口（completion 终稿、状态翻转、飞书同步）待 PM 确认后执行。

## 一、验收范围与证据分层

- 范围：v0.4 [需求](../../../docs/versions/v0.4.0/requirements.md)五条验收标准、账单纵向场景 [BF01—BF07](../../../.scratch/v04-bills/spec.md)、完整前端、安全能力与评测、平台真实账单模块接入（[Issue #123](https://github.com/DrErwin/hackerthon-bank-agent/issues/123)）。
- 证据分层（**不同层不互相替代**）：业务/HTTP 实跑 72 条 ＞ 单元/算术 147 项 ＞ 真实模型批次 A 24 轮 ＞ 页面（离线 24/24 检查 + PM 本人 6 步走查）。单元层全绿不推导业务通过；模拟器与替身不推导真实模型或专业安全结论。

## 二、BF01—BF07 逐项证据

| 编号 | 场景 | 现有可复核证据 | 结论 |
|---|---|---|---|
| BF01 | 查询与分类统计主路径（含口语化表达） | [L01 公共业务 17 条实跑 17/17](../../../evals/bills/README-public-06.md)（[PR #198](https://github.com/DrErwin/hackerthon-bank-agent/pull/198)）；HTTP 汇总/明细 `BILL-HTTP-X01/X02`；L03 真实模型报告数字与银行流水逐项对账（18 笔一致） | ✅ 含例外 E3 |
| BF02 | 异常识别（四规则命中与不命中、边界） | [L02 公共入口 14 条 14/14 + 四规则 12 条对照 12/12](../../../evals/bills/README-public-coverage-v2.md)（[PR #209](https://github.com/DrErwin/hackerthon-bank-agent/pull/209)）；HTTP 候选/扫描/空候选 `BILL-HTTP-X04/X05/X06`；规则 3 第三例为"不适用（noneligible）"，未谎称"信息不足" | ✅ 含例外 E1 |
| BF03 | 月度/年度报告（总览/分类/对比、范围不足） | [L03 公共入口 14 条 14/14](../../../evals/bills/README-public-coverage-v2.md)；`BILL-HTTP-01` 报告与真实流水独立复算；[真实 GLM L03 默认运行时验收（2 次运行数字一致）](../../../.scratch/v04-platform/evidence/2026-10-20/2026-10-20-l03-default-runtime-acceptance.md) | ✅ |
| BF04 | 导出与权限（两层导出、明细再验证、越权） | [HTTP 15 场景 15/15](../../../evals/bills/README-http-current-07.md)（[PR #210](https://github.com/DrErwin/hackerthon-bank-agent/pull/210)）：`BILL-HTTP-02/03` 卡片与明细两层导出、`04` 连续错误验证码、`05` 验证过期、`06` 跨用户 404、`07` 会话变化后旧文件失效；`X08` CSV 公式型文本安全前缀；F22/F24 `no-store`、无逐笔 ID | ✅ 含例外 E1、E2 |
| BF05 | 缺信息追问与口径纠正 | 17 条 L01 中的澄清类（`BILL-PUBLIC-02/03/13/16/17`）+ L02 缺月/选账户/含糊金额/无匹配（`05—08`）+ L03 缺期/比较/未来期间/类别澄清（`05—08`）+ `BILL-HTTP-X03` | ✅ 含例外 E3 |
| BF06 | 中断与恢复（同一任务、失败与数据不足） | L01 `BILL-PUBLIC-07/08/09/10/11/12/14/15`（银行范围拒绝、B01/B08 失败后沿原任务恢复、退款原单取数失败后恢复、跨会话恢复）；L02 `10—14`（取消、重放、权限撤销、会话恢复）；L03 `09—11`；HTTP `04/05/07`、`X03/X06/X07` | ✅ 含例外 E5 |
| BF07 | 前端账单插槽走查 | [票 04 真实接口联调 5 场景 98 断言](../../../.scratch/liangshuang-frontend-complete/evidence/2026-10-21-real-api-bills-slot.md)（[PR #199](https://github.com/DrErwin/hackerthon-bank-agent/pull/199)）；[票 05 主入口替换与全面回归](../../../.scratch/liangshuang-frontend-complete/evidence/2026-10-21-replace-entry-and-regress.md)（[PR #201](https://github.com/DrErwin/hackerthon-bank-agent/pull/201)）：`npm test` 38 passed、build 通过、双场景走查；PM 2026-10-21 验收通过（单会话、不部署） | ✅ 含例外 E6 |

## 三、覆盖数量（按现有实跑，不补量）

| 层 | 数量 | 实跑结果 |
|---|---|---|
| L01 公共业务场景 | 17 | 17/17 passed（[证据与台账](../../../evals/bills/run-log-public-06.md)） |
| L02 公共入口 | 14 | 14/14 passed |
| L03 公共入口 | 14 | 14/14 passed |
| 四类异常规则对照 | 12 | 12/12 passed（[合计 40/40，含前两项](../../../evals/bills/run-log-public-coverage-v2.md)） |
| HTTP 端到端 | 15 | 15/15 passed，128 次真实请求（[台账](../../../evals/bills/run-log-http-current-07.md)） |
| **业务/HTTP 合计** | **72** | **全部 passed；零资金提交、银行表摘要前后不变** |
| 私有算术 + 工具（单元层） | 147 | 147 passed（130 算术 + 17 工具；**不计入业务覆盖**） |

数量门对照（[评测指南 §三](../../../evals/README.md)）：**每功能 ≥10 条**——L01 20 / L02 30 / L03 22（含 HTTP 归属用例）✅；**每类异常 ≥3 条**——四规则各 3 条对照 ✅；**每种错误 ≥3 条**——未补齐，登记为例外 E1。旧文档的 96 条是设计索引，不是通过数。

## 四、v0.4 验收标准逐条对应

| 标准（[需求](../../../docs/versions/v0.4.0/requirements.md)） | 对应证据 | 结论 |
|---|---|---|
| 1. 账单与订阅复用 v0.3 公共框架 | 账单 L01/L02/L03 全部经同一 Harness、公共契约、安全门、银行接缝与审计（[平台票 05](../../../.scratch/v04-platform/issues/05-real-bills-integration.md) 阶段一/二验收）；订阅场景 05 于 2026-10-19 收口 | ✅ |
| 2. 业务模块不直接访问其他模块私有工具或银行表 | 账单以公共能力注册与 `public_catalog()` 身份断言覆盖（L01/L02/L03 均验证真实 manifest 而非桩）；评测断言走真实公共入口与 BankGateway | ✅ |
| 3. 敏感动作逐笔确认与安全检查 | 转账确认/验证闭环未回退（[票 05 回归](../../../.scratch/liangshuang-frontend-complete/evidence/2026-10-21-replace-entry-and-regress.md)）；明细导出必须再验证（`BILL-HTTP-03/04/05`，验证前无明细读数）；订阅退订写前快照（#164/#191） | ✅ |
| 4. 当期场景业务与安全评测达到 PRD 标准 | 业务 72 条实跑全过 + 单元 147；安全[离线全量 20 Passed / 0 Failed / 337 Blocked](../../../evals/security/offline-2026-10-21-closeout.md)（138/295/357，891 断言 0 失败）、[批次 A 24 轮真实模型](../../../evals/security/evidence/2026-10-21/live-2026-10-21-batchA-README.md)、页面离线 24/24 | ✅ 含例外 E1/E5/E7/E9 |
| 5. 完整前端替换后重跑关键闭环且不回退 | 主入口已替换并保留 `/legacy`；确认、验证、刷新只读恢复、重复点击只提交一次、账单 5 场景全部重跑通过；390×844 与 1280×800 适老化走查 `PASS_WITH_WAIVERS`（硬门槛 0 失败） | ✅ 含例外 E6/E10 |

## 五、安全线证据（离线 + 真实模型 + 页面）

- **离线全量**：138/295/357 用例，**20 Passed / 0 Failed / 337 Blocked**，891 条断言 0 失败，真实模型 0；覆盖审计与数量门（[#211](https://github.com/DrErwin/hackerthon-bank-agent/pull/211)）、三类观察端入口（[#212](https://github.com/DrErwin/hackerthon-bank-agent/pull/212)）、全量重跑与检测器三档（[#213](https://github.com/DrErwin/hackerthon-bank-agent/pull/213)）。
- **真实模型批次 A**：GLM-5.3 @ Coding Plan 业务链 24 轮，**3 Passed / 0 Failed / 21 Blocked**（147 断言 0 失败；Blocked 是脚本不自动判解释的预期项）；§4.4 解释复核 21 轮 **21/21 符合**（PM 2026-10-21 23:55 口头确认；安全侧真人复核仍缺）。
- **页面**：离线 Playwright 回归 SEC-C-001 9/9、SEC-P-002 15/15（24 项检查全过、0 模型调用）；真实模型页面 6 步走查由 **PM Erwin 本人操作并于 2026-10-22 00:17 验收通过**，AI 按 PM 选择补跑缺项并截图（[记录](../../../evals/security/evidence/2026-10-21-live/page-walkthrough-2026-10-22.md)）。
- **批次 B 39 轮 gated**：仅保留"门确实拦住"的零费用证据（39 Blocked、`called=false`、0 模型调用），**不记作验证**；批次 C（三类观察端接真实模型）缺平台接缝与模型预算。
- **关闭留痕**：#86、#88 于 2026-10-22 由 PM 决定关闭；**关闭 ≠ Ringo 本人签核**，例外登记不变。

## 六、前端与订阅

- 前端票 03/04/05 全部合入：[#142](https://github.com/DrErwin/hackerthon-bank-agent/pull/142)（转账插槽，真实接口走查 PASS）、[#199](https://github.com/DrErwin/hackerthon-bank-agent/pull/199)（账单插槽）、[#201](https://github.com/DrErwin/hackerthon-bank-agent/pull/201)（主入口替换 + 全面回归）；评测脚本适配 [#202](https://github.com/DrErwin/hackerthon-bank-agent/pull/202)/[#203](https://github.com/DrErwin/hackerthon-bank-agent/pull/203) 并在干净提交复跑（安全 React 9/9 与 15/15；转账 OBS-03/04/06/07 Passed，OBS-05 Blocked → 例外 E10）。
- PM 2026-10-21 验收口径：完整前端**单会话、不做服务器部署**（演示界面即可），已按此验；不等于 Ringo 安全签核。
- 订阅场景 05：2026-10-19 收口（7 张实施票 + 1 张底座修复票合入，评测 48 条、B29/B30 银行接缝、退订写前快照），证据见 `evals/subscription/evidence/2026-10-19/`。

## 七、例外清单

| 编号 | 例外 | 影响与登记 |
|---|---|---|
| E1 | **每种错误 ≥3 条未补齐**（约 13 条）：导出技术故障 3、报告资源读写故障 3、验证码重发/取消/重复提交 3、恶意 HTML 全链路 2、银行范围拒绝 1、用户取消 1 | PM 2026-10-22 决定不硬凑；BF02/BF04/BF05 的"通过"以现有用例为限，不推定全覆盖 |
| E2 | 导出场景用例 8 条（HTTP 7 + X08） | 按三个公开能力计数量门已达标；若按"导出功能 ≥10"口径差 2 条，并入 E1 不另补 |
| E3 | L01 剩余缺口：非正净额、环比/同比黄金数据、精确边界、更多错误变体 | 已在[覆盖表](../../../evals/bills/coverage-matrix.md)与[缺口文档](../../../evals/bills/gaps.md)登记；未单独补用例 |
| E4 | 账单票内未并入真实模型与 React 页面 | 真实 GLM 平台侧证据（[票 05 阶段二](../../../.scratch/v04-platform/evidence/2026-10-20/2026-10-20-l03-default-runtime-acceptance.md)）与前端票 04/05 证据独立存在，不混算成同一次运行 |
| E5 | SSE 正向重连/失效未覆盖 | 票 07 已如实登记；不阻塞 BF 结论，属后续补测 |
| E6 | 部署形态（TCP/TLS）、真机软键盘、多会话未验证 | 按 PM 2026-10-21 口径只验单会话、不部署，已作例外接受 |
| E7 | 安全侧：批次 B 39 轮未解门验证、批次 C 观察端未接真实模型、§4.4 安全侧真人复核缺 | 如实保留；不写成已验证 |
| E8 | Ringo 真人安全签核缺 | #86/#88 由 PM 决定关闭，**非本人签核**；代行记录不变 |
| E9 | 安全评测数量门例外：29 项验收条目关联主用例 <10（差额 170） | PM 2026-10-21 决定 A 接受；[覆盖审计](../../../evals/security/coverage-audit-2026-10-21.md)登记 |
| E10 | 转账 OBS-05 Blocked（完整前端单会话入口无"切换对话"动作） | 等价保护由 `ui-recovery.test.tsx` 覆盖，不伪装通过 |

## 八、结论

- **BF01—BF07：按现有证据视为通过，含 E1—E10 例外**；不使用"全部通过"或"无缺口"表述。
- **v0.4 五条验收标准**：第 1—3 条证据齐全；第 4、5 条有实跑与真实模型/页面证据，缺口已在例外登记。
- 本记录**只完成联合验收的证据汇总与逐项判定**；`completion.md` 终稿、`docs/README` 与 `ROADMAP` 状态翻转、飞书同步、v0.5 启动确认**待 PM Erwin 确认后执行**。
- 代行记录：PM 授权、AI 整理与审查；**非 Ringo 本人审查**；例外不因收口消失。

## 九、证据索引

- 账单评测：[17 条 L01](../../../evals/bills/README-public-06.md)、[40 条 L02/L03/规则对照](../../../evals/bills/README-public-coverage-v2.md)、[15 条 HTTP](../../../evals/bills/README-http-current-07.md)、[台账](../../../evals/bills/run-log.md)、[覆盖表](../../../evals/bills/coverage-matrix.md)、[缺口](../../../evals/bills/gaps.md)。
- 平台/纵向：[平台票 05](../../../.scratch/v04-platform/issues/05-real-bills-integration.md)、[L03 默认运行时验收证据](../../../.scratch/v04-platform/evidence/2026-10-20/2026-10-20-l03-default-runtime-acceptance.md)、[Issue #123](https://github.com/DrErwin/hackerthon-bank-agent/issues/123)（已关闭）。
- 安全：[离线收尾与检测器三档](../../../evals/security/offline-2026-10-21-closeout.md)、[覆盖审计](../../../evals/security/coverage-audit-2026-10-21.md)、[联调清单](../../../evals/security/live-model-page-run-plan.md)、[批次 A 归档说明](../../../evals/security/evidence/2026-10-21/live-2026-10-21-batchA-README.md)、[页面走查记录](../../../evals/security/evidence/2026-10-21-live/page-walkthrough-2026-10-22.md)、[台账](../../../evals/security/run-log.md)。
- 前端：[票 04 联调证据](../../../.scratch/liangshuang-frontend-complete/evidence/2026-10-21-real-api-bills-slot.md)、[票 05 替换与回归](../../../.scratch/liangshuang-frontend-complete/evidence/2026-10-21-replace-entry-and-regress.md)、[票 03 真实接口走查](../../../.scratch/liangshuang-frontend-complete/evidence/2026-10-20-real-api-walkthrough.md)。
- 版本：[完成情况](../../../docs/versions/v0.4.0/completion.md)、[需求](../../../docs/versions/v0.4.0/requirements.md)、[交付包 02](../../../.scratch/v04-bills/packages/02-v04-acceptance.md)。
