# 交付包 01：v0.4 账单业务能力与评测

Status: in_progress（2026-10-11 周恩宇已接受并开始本模块局部实施；公开链路依赖见 Issue #91）
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
