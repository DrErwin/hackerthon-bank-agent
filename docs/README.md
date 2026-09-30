# AI Banking Agent 文档版本进度

本项目为银发人群提供自然语言银行助理。长期事实文档继续按内容日期维护；本页使用需求里程碑号追踪每个阶段原本要做什么、实际完成了什么。

## 当前进度

- 最新完成里程碑：**v0.2.0 · 公共契约与架构基线**
- 当前里程碑：**v0.3.0 · 普通转账纵向链路**（进行中）
- 下一计划里程碑：**v0.4.0 · 账单、联动与完整安全扩展**

截至 2026-09-30，v0.3 的后端核心模块与模拟银行评测已合入并通过本地测试；任务 API、React 前端、专业安全与转账评测及全链路联合验收仍待完成。具体证据和遗留见[v0.3 完成情况](versions/v0.3.0/completion.md)。

这里的版本号是需求里程碑号，不等同于软件包或对外发布版本。PRD、架构和契约仍使用日期文件名，并作为跨版本事实来源。

## 版本列表

| 版本 | 阶段 | 状态 | 需求 | 完成情况 | 阶段资料 |
|---|---|---|---|---|---|
| v0.1.0 | PRD 与业务范围基线 | 已完成 | [需求](versions/v0.1.0/requirements.md) | [完成情况](versions/v0.1.0/completion.md) | — |
| v0.2.0 | 公共契约与架构基线 | 已完成 | [需求](versions/v0.2.0/requirements.md) | [完成情况](versions/v0.2.0/completion.md) | — |
| v0.3.0 | 普通转账纵向链路（目标 10-12 收口） | 进行中 | [需求](versions/v0.3.0/requirements.md) | [完成情况](versions/v0.3.0/completion.md) | [实施计划](versions/v0.3.0/implementation-plan.md) |
| v0.4.0 | 账单、联动与完整安全扩展（目标 10-20） | 计划中 | [需求](versions/v0.4.0/requirements.md) | [完成情况](versions/v0.4.0/completion.md) | — |
| v0.5.0 | 系统验收与体验打磨（目标 10-30） | 计划中 | [需求](versions/v0.5.0/requirements.md) | [完成情况](versions/v0.5.0/completion.md) | — |
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
