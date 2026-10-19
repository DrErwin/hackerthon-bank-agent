# AI Banking Agent 文档版本进度

本项目为银发人群提供自然语言银行助理。长期事实文档继续按内容日期维护；本页使用需求里程碑号追踪每个阶段原本要做什么、实际完成了什么。

## 当前进度

- 最新完成里程碑：**v0.3.0 · 普通转账纵向链路**（2026-10-11 收口，含明示例外）
- 当前里程碑：**v0.4.0 · 账单、完整安全、完整前端与订阅代扣**（2026-10-11 启动，提前于原 10-13；2026-10-19 新增场景 05 订阅 / 代扣管理；**最晚 10-20 收口**〔PM 硬截止〕，联动移至 v0.5）
- 上一里程碑：**v0.2.0 · 公共契约与架构基线**
- v0.4 进展速览（2026-10-20 收口日）：平台/底座线全部合入（含票 05 阶段一 L01 真实链路经独立检查验收通过，[#143](https://github.com/DrErwin/hackerthon-bank-agent/pull/143) / [#144](https://github.com/DrErwin/hackerthon-bank-agent/pull/144)）；账单 L01/L03 与评测 [#93](https://github.com/DrErwin/hackerthon-bank-agent/pull/93)、审计证据收窄 [#171](https://github.com/DrErwin/hackerthon-bank-agent/pull/171) 已合入（[Issue #145](https://github.com/DrErwin/hackerthon-bank-agent/issues/145) 关闭）；[订阅场景 05](../.scratch/v04-subscription/spec.md) 票 09/10 已合入（完整验收集 17→48 条）；前端通用底盘 + 票 03 转账真实接口（[PR #142](https://github.com/DrErwin/hackerthon-bank-agent/pull/142)，真实接口走查 PASS）。**2026-10-20 01:45 PM 决定：前端票 04 账单插槽、票 05 替换简易前端与全面回归留在本期完成、不顺延**（同日 01:41 的顺延记录作废；硬前置＝平台注册 L03 + 安全白名单收录 `REPORT_MANIFEST`）；安全线三张 Ready（[#149](https://github.com/DrErwin/hackerthon-bank-agent/pull/149) / [#159](https://github.com/DrErwin/hackerthon-bank-agent/pull/159) / [#162](https://github.com/DrErwin/hackerthon-bank-agent/pull/162)）已出独立审查结论，Draft 链 #163→#165→#169→#170 等前置。详见[v0.4 完成情况](versions/v0.4.0/completion.md)。

截至2026-10-11，v0.3 已收口（含明示例外）：转账评测（全量153样本153 Passed、标准21/21、业务红线Passed、缺项8/8）与安全评测证据链（全量离线20 Passed/0 Failed/310 Blocked、真实GLM 57轮与转正24轮、React页面证据、解释口径复核、S07—S09与导出失败分支补齐、SEC-N-008收口、Issue #79修复）均已入库；[AF01—AF14与T01—T18联合验收证据表](versions/v0.3.0/acceptance-evidence-2026-10-10.md)、[安全评测全量适用性核查](../evals/security/coverage-audit-2026-10-11.md)与 Ringo 侧[适用性复核/专业意见/攻击来源材料](../evals/security/applicability-review-2026-10-10.md)已出具，TF-VFY-16 材料已接入复跑完成。**例外**：Ringo 本人签核已由项目负责人豁免（2026-10-11，PM 规则免审即豁免；适用性复核/专业意见/攻击来源材料已入库供追溯）；R06 差 2 条、8 个维度组低于 10 条；规划入口上下文与确认/验证历史回放为底座后续；真实威胁检测移出本次验收。上述待补项保留在 [Issue #86](https://github.com/DrErwin/hackerthon-bank-agent/issues/86) 等，完成后补验加回。前端规范与普通转账原型 v0.1 已于2026-10-06入库；完整前端已开工——原型五类画面 10-12 补齐并走查通过，通用底盘 PR #108（10-13）与转账票 03 真实接口 PR #142（10-20，真实接口走查 PASS）均已合入；账单插槽（票 04）与主入口替换 + 全面回归（票 05）按 PM 2026-10-20 决定留在 v0.4 内完成、不顺延。具体证据、例外与遗留见[v0.3完成情况](versions/v0.3.0/completion.md)。

这里的版本号是需求里程碑号，不等同于软件包或对外发布版本。PRD、架构和契约仍使用日期文件名，并作为跨版本事实来源。

## 版本列表

| 版本 | 阶段 | 状态 | 需求 | 完成情况 | 阶段资料 |
|---|---|---|---|---|---|
| v0.1.0 | PRD 与业务范围基线 | 已完成 | [需求](versions/v0.1.0/requirements.md) | [完成情况](versions/v0.1.0/completion.md) | — |
| v0.2.0 | 公共契约与架构基线 | 已完成 | [需求](versions/v0.2.0/requirements.md) | [完成情况](versions/v0.2.0/completion.md) | — |
| v0.3.0 | 普通转账纵向链路（目标 10-12 收口） | 已收口（含明示例外） | [需求](versions/v0.3.0/requirements.md) | [完成情况](versions/v0.3.0/completion.md) | [实施计划](versions/v0.3.0/implementation-plan.md) |
| v0.4.0 | 账单、完整安全与完整前端（最晚 10-20 收口；联动移至 v0.5） | **进行中**（2026-10-11 启动；2026-10-20 收口日） | [需求](versions/v0.4.0/requirements.md) | [完成情况](versions/v0.4.0/completion.md) | — |
| v0.5.0 | 联动、系统验收与体验打磨（目标 10-30） | 计划中 | [需求](versions/v0.5.0/requirements.md) | [完成情况](versions/v0.5.0/completion.md) | — |
| v1.0.0 | 比赛交付（截止 11-02） | 计划中 | [需求](versions/v1.0.0/requirements.md) | [完成情况](versions/v1.0.0/completion.md) | — |

## 项目总体文档

- [完整文档索引](00-项目文档索引.md)
- [正式项目跟踪](01-项目跟踪.md)
- [Roadmap](pm/ROADMAP.md)
- [系统架构基线](architecture/system-framework-2026-09-19.md)
- [公共契约](contracts/公共契约-2026-09-23.md)
- [跨团队纵向交付与版本进度原则](principles/04-cross-team-delivery.md)

## 阅读与维护

- 看某阶段承诺：打开该版本的 `requirements.md`。
- 看某阶段事实：打开该版本的 `completion.md`。
- 看负责人、排期和实时状态：查看 `01-项目跟踪.md` 与飞书进度表。
- 看当前工程规格和任务：查看 `.scratch/`。
- 进入下一里程碑前，先更新当前版本的 `completion.md`，写明验证证据、差异和遗留。
- 新增未来需求时先放入对应计划版本，不为未来版本提前创建实施票。
