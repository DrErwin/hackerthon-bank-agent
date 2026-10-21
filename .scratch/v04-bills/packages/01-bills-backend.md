# 交付包 01：v0.4 账单业务能力与评测

Status: done（2026-10-22 收口，含例外：票 01—10 已合入，票 06/07 按 PM 决定以现有证据收口；BF01—BF07 判定与例外见[联合验收记录](../../../docs/versions/v0.4.0/acceptance-evidence-2026-10-22.md)；不写"全部通过"，真人安全签核仍缺）
Owner: 周恩宇（Ethan / @zhouey314-cloud）
Activation: 2026-10-11 Erwin 建立（v0.4 正式启动同日）
Start when: v0.4 已于 2026-10-11 正式启动；[02 账单 PRD](../../../docs/prd/02-账单分析-PRD-2026-09-23.md)与[公共契约](../../../docs/contracts/公共契约-2026-09-23.md)已冻结、[21 条代表性用例](../../../evals/bills/)已合入——接包即可 `to-spec → to-tickets`
Spec: [v0.4 账单纵向场景规格](../spec.md)

Accepted by: 周恩宇（Ethan / @zhouey314-cloud；本人本轮明确要求按仓库完成并提交）
Accepted at: 2026-10-11
Work spec: [v04-ethan-bills-backend 账单实施规格](../../v04-ethan-bills-backend/spec.md)

Source issue: [Issue #87](https://github.com/DrErwin/hackerthon-bank-agent/issues/87) 总索引（账单线）；延续[交付包 04：后续业务评测准备](../../transfer-agent-framework/packages/04-v04-eval-preparation.md)的评测准备成果

## 业务目标

账单三类公开能力（查询与分类统计、异常交易识别、月度/年度报告与导出）在 v0.3 公共框架上落地，评测达到下限并实跑归档；账单公开能力接口形态确定后向前端工作线发出冻结信号，支撑双场景前端接入。

## 交付范围

1. **业务能力**：`backend/app/modules/bills/` 按 02 PRD 实现三类公开能力；只调用公开能力与银行接缝，不访问其他模块私有工具或银行表。
2. **评测**：`evals/bills/` 从 21 条代表性用例扩充到完整规模下限（每功能至少 10 条、每类异常至少 3 条），接入账单能力后实跑，证据归档 `evals/bills/evidence/`。
3. **接口形态冻结信号**：账单公开能力接口形态确定后即通知前端工作线（[frontend-complete/01](../../frontend-complete/packages/01-v04-complete-frontend.md) 账单插槽的接入条件）；发现契约缺口按[公共改动流程](../../../docs/principles/03-review-and-merge.md)登记，由公共目录负责人修改，不自行改契约。

不在本包范围：跨场景联动（v0.5）、前端页面实现（frontend-complete/01）、模拟银行改动（需要时登记依赖由底座实施）。

## 向其他工作线提供什么

- 可运行的账单公开能力（后端）。
- 账单接口形态冻结信号 → 前端账单插槽开工。
- 评测运行证据 → [交付包 02 联合验收](02-v04-acceptance.md)。

## 验收标准

对应[场景规格 BF01—BF07](../spec.md)。要点：

1. BF01—BF06 通过；账单结论有流水依据，查询失败/数据不足不编数字。
2. 明细导出必须再次身份验证；越权拒绝；商户名不打码、账号打码。
3. 异常识别只提示与解释，不把疑似说成确认，不代用户执行场景 04/05。
4. 一级读取登录即可，不额外加验证门槛。
5. 评测覆盖表齐、下限达标、实跑证据入 `evidence/`；文档/自动化/运行结果分别记录。
6. 一张票只对应一个目录：bills 实现票与 evals 评测票分开；涉底座或模拟银行的数据改动登记依赖，不跨目录改。

## 负责人接受后怎样拆自己的票

- 接包后走 `to-spec → to-tickets`：建议沿用 `v04-ethan-bills-eval` 工作组扩编或新设本人工作组（由本人定，遵守[票据标识规范](../../../docs/agents/issue-tracker.md)）。
- 评测按[评测工程四步](../../../evals/README.md)推进：规格与用例 → 领域测试数据 → 自动化实现 → 证据回填；账单流水样本数据放 `evals/bills/fixtures/` 或本人目录，涉模拟银行共享种子由底座（Erwin）单独实施，本人只登记依赖。
- 路径就绪即联调：接口形态冻结即通知前端；能力部分可跑时先贯通 BF01 主路径，异常与导出分支随后逐步验收。

## 备注

- 联动（cross）评测准备（23 条）已随联动移至 v0.5，本包不包含、不重开交付包 04。
- 底座 #84/#85 与安全线 #86/#88 并行推进，与本包无硬依赖；公开契约若有变更按变更流程通知。

## 2026-10-11 本人启动记录与边界

已接受新包，新工作组 [v04-ethan-bills-backend](../../v04-ethan-bills-backend/spec.md)；原代表性评测包和票保持已验收，不重新打开。本人过程台账见 [progress.md](../../v04-ethan-bills-backend/progress.md)。

实际代码检查发现银行接入层 B08 与账单公共类型尚待实现，已登记 [Issue #91](https://github.com/DrErwin/hackerthon-bank-agent/issues/91) 给 Erwin。先做本模块私有统计内核、局部测试与覆盖/数据，不修改公共目录、不伪造注册入口或权限通过。局部65项模块测试与26个算术黄金样本合跑91项通过；L01—L03真实业务、HTTP/模型/页面未验证，整包仍in_progress。该事实不改变原本BF01—BF07验收要求。

## 2026-10-20 账单线交付状态（AI 代填 · 非真人审查）

- **已合入**：L01 最小切片（[#131](https://github.com/DrErwin/hackerthon-bank-agent/pull/131) `85a119d`）、L03 类型化报告（[#151](https://github.com/DrErwin/hackerthon-bank-agent/pull/151) `40a61c3`——复审「可合」，比较意图与未来月份拦截实测有效，模块 214 passed）、评测覆盖与 head 绑定证据（[#93](https://github.com/DrErwin/hackerthon-bank-agent/pull/93) `c2f9067`——147 passed：130 算术 + 17 工具；Actions artifact 与入库 gzip 逐字节一致）、读路径审计证据收窄（[#171](https://github.com/DrErwin/hackerthon-bank-agent/pull/171) `f119482`，[Issue #145](https://github.com/DrErwin/hackerthon-bank-agent/issues/145) 已关闭）。
- **未合 / 未开 PR**：L02 私有规则分支 `feat/bills/l02-private-rules` 与 [Issue #136](https://github.com/DrErwin/hackerthon-bank-agent/issues/136) 票 09 分支 `test/bills/l01-module-dedup-136-09` 仍未开 PR（受「一人最多两张未合 PR」限制）；#136 保持 OPEN。
- **跨线前置**：L03 `bills.generate_report` 尚未在平台注册、安全白名单只收 L01 → 前端票 04 账单插槽真实联调不可用（见 [平台票 05](../v04-platform/issues/05-real-bills-integration.md) 2026-10-20 留痕）。
- **BF 口径（如实）**：BF01/BF03/BF05/BF06 仅有部分算术断言；BF02/BF04/BF07 未完成；96 条设计 ≠ 96 条全部通过，评测证据只覆盖 147 项算术/工具合跑。

## 2026-10-21 · 交付包01最新个人交付记录（AI过程更新，非联合验收）
- 账单 L01/L02/L03及返修相关PR #92/#131/#140/#151/#171/#182/#183已合并；#188联动[PR #197](https://github.com/DrErwin/hackerthon-bank-agent/pull/197) 已合，安全L02白名单 #196、平台注册 #192亦已合入，当前能力不再标记为“未注册”。
- 业务评测 [PR #198](https://github.com/DrErwin/hackerthon-bank-agent/pull/198) 已合入，L01一期17个真实公共业务场景有固定源Actions实跑17/17及原始证据；**不是**所有功能评测达到数量下限。
- 票07 [PR #208](https://github.com/DrErwin/hackerthon-bank-agent/pull/208) 已发起审查，历史固定源7个真实HTTP场景/87请求专项7/7成功且原始证据归档；新主线专项运行与缺失场景仍在进行，不能因普通CI通过即等同专项通过。
- 前端 #199/#201 已合入，其独立真实接口及浏览器验收证据由前端线记录；项目平台 [Issue #123](https://github.com/DrErwin/hackerthon-bank-agent/issues/123) 仍开放，安全专业批准也不由账单Owner代签。个人10张票中01/02/03/04/05/08/09/10为已合入子范围；06/07 `in_progress`。BF01—BF07完整联合验收和评测数量下限未核销，**整个交付包仍 `in_progress`**。

## 2026-10-21 晚 · 票06/07 实跑并入 main（AI 代行，非联合验收）

- 票06 [PR #209](https://github.com/DrErwin/hackerthon-bank-agent/pull/209) `4b32b98`：L02/L03/异常规则对照 40 条，实跑 **40/40 passed**，143 份源码 blob 校验、零资金提交；首跑 12 条失败为测试读取非公开字段，已最小修复（未放宽断言），失败证据保留。
- 票07 [PR #210](https://github.com/DrErwin/hackerthon-bank-agent/pull/210) `c27d23c`：当前 main 上 15 个 HTTP 场景、**128 次请求，15/15 passed**，145 份源码校验、64 个真实导入、逐例零资金提交；[PR #208](https://github.com/DrErwin/hackerthon-bank-agent/pull/208) `0d829d5` 为历史源码 7 场景/87 请求证据。
- 合并留痕：PM Erwin 授权代行跑证据与合并、AI 实施与审查、非 Ethan 本人审查；两票仍 `partial`，BF01—BF07 联合验收、真实模型/页面与专业安全未覆盖，整包不写 accepted。

## 2026-10-22 交付包收口（含例外）

- 票 06/07 于同日收口为"已完成、含例外"：业务/HTTP 实跑 72 条全过（L01 17、L02 14、L03 14、规则对照 12、HTTP 15），单元层 147 项单独计数。
- PM Erwin 2026-10-22 决定不硬凑指标：每种错误 ≥3 的约 13 条补量不做，登记为[联合验收例外 E1](../../../docs/versions/v0.4.0/acceptance-evidence-2026-10-22.md)；真实模型/页面与 Ringo 真人签核另记。
- BF01—BF07 逐项判定、版本五条验收标准对应与完整例外清单见[v0.4 联合验收记录](../../../docs/versions/v0.4.0/acceptance-evidence-2026-10-22.md)。
- 代行记录：PM 授权、AI 实施与审查，非 Ethan 本人审查；本包不代签安全结论。
