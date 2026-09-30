# AGENTS.md

AI Banking Agent：为银发人群打造的银行智能助理，用自然语言理解金融意图并代理执行转账、账单、跨场景联动等业务，配权限分级、敏感确认与注入防御。

架构真相源：[docs/architecture/system-framework-2026-09-19.md](docs/architecture/system-framework-2026-09-19.md)。技术栈：Python 后端（FastAPI + Pydantic + Deep Agents/LangGraph），前端 React（2026-09-29 由 Vue3 改定）。

## 目录边界

一次只负责一个目录，改动只落在你被分配的目录内：

| 目录 | 归属 |
|---|---|
| `backend/app/contracts/` `api/` `agent_platform/` | 底座（Erwin） |
| `backend/app/audit/` | 底座（Erwin）：运行日志写入与只读回放；审计规则由安全侧定 |
| `backend/app/security/` | 安全（Ringo）：策略、执行器、确认；审计与记忆的安全规则 |
| `backend/app/memory/` | 底座（Erwin）：Agent 长期记忆与上下文后端，随 harness 走；安全规则由安全侧定 |
| `backend/app/modules/transfer/` | 转账（梁爽） |
| `backend/app/modules/bills/` | 账单（周恩宇；2026-09-28 全员会起由六水移交） |
| `backend/app/modules/cross/` | 联动（周恩宇） |
| `backend/app/services/` `storage/` | 底座共享 |
| `frontend/` | 前端 / 适老化（梁爽负责，六水协助；2026-09-25 确认） |
| `evals/` | 评测集，按子目录归属：transfer Erwin · bills 周恩宇 · cross 周恩宇 · security Ringo · mockbank Erwin（2026-09-28 全员会调整） |

### v0.3 临时执行安排（2026-09-27）

为尽快跑通普通转账纵向链路，v0.3 由 Erwin 依次实现底座、最小安全门和普通转账参考路径，并接手转账评测及对应审查（2026-09-28 全员会定，原为梁爽）；Ringo 负责安全评测及审查。该安排只适用于 v0.3 首条路径，不改变安全与转账目录的长期归属；阶段收口后，后续维护回到上表负责人。

同一个人可以按顺序承担多个目录，但一张实施票、一个分支和一个 PR 仍只对应一个目录，禁止把底座、安全和转账做成一个无法独立审查的大改动。

## 开工先读

- 队员说明身份、询问下一步、领取交付包或开始工作 → 必须先读[队员开工与通用 Skill](docs/agents/delivery-workflow.md)：定位本人交付包，明确接受后自动记录领取，检查并安装缺失的通用 Skill，再按 `to-spec → to-tickets → 按票执行` 推进；有开发票时使用 `implement`。不能直接给工作清单跳过接包和拆票。
- 任何提交与分支操作 → [Git 与提交约定](docs/agents/git-workflow.md)
- 写或改业务模块 → [业务并行原则](docs/principles/01-business-parallel.md)
- 写或改安全底座 / 执行器 / 审计 → [安全底座原则](docs/principles/02-security-platform.md)
- 开分支、提 PR、审查合并 → [Review 与合并原则](docs/principles/03-review-and-merge.md)
- 拆跨团队纵向场景、交付包或版本进度 → [跨团队纵向交付与版本进度原则](docs/principles/04-cross-team-delivery.md)

## 三条铁律

1. **LLM 只动嘴不动手**：模型只理解、规划、回复；执行权在确定性代码手里。
2. **动钱必过确认门**：敏感操作暂停 → 前端确认 → 沿原任务继续。
3. **银行规则只在模拟银行**：结果只认银行返回，不复刻余额、限额、风控规则。

## 提交前自查

- 工具已声明权限、副作用、确认策略。
- 测试覆盖：正常、关键分支、暂停恢复、权限拒绝、异常兜底。
- 引用公共契约，不复制一份。
- PR 说明：场景编号、依赖、是否触及安全或契约。

## 飞书同步工具

`docs/` 是唯一事实源，飞书是阅读端，方向只出不回。同步由人决定何时执行，命令如下：

```bash
python tools/feishu_sync.py plan      # 只看会推哪些文档，不碰飞书
python tools/feishu_sync.py publish   # 推内容：缺失的新建、已存在的原地覆盖
python tools/feishu_sync.py mount     # 把还没进知识库的挂进对应分区（幂等）
```

飞书使用 `tools/feishu_publish_all.py` 中的 `CURATED_SOURCES` 白名单，分三层发布：当前工作台与当前版本、项目 Roadmap 与版本总览、已冻结且跨阶段复用的 PRD / 架构 / 契约 / 协作规则。模板、会议稿、研究过程和收口过程记录只留仓库或 Drive 归档。新增文档先留在仓库，只有项目负责人确认属于上述三层后才加入白名单。已退出白名单的资料用 `archive-plan` 检查、`archive` 移出知识库并保留到 Drive 归档，不直接删除。

飞书按标题识别文档；已发布标题固定在 `TITLE_OVERRIDES`，改标题会新建一篇。同步当前工作台后重新运行 `python tools/embed_stages.py`，因为覆盖正文会移除内嵌甘特图。

## Agent skills

### Issue tracker

规格与实施票放在 `.scratch/`。新建、引用或领取票据时先读[票据标识规范](docs/agents/issue-tracker.md)：组内分别编号，对外使用完整票号 `<feature-slug>/<NN>`、标题及链接；交付包、实施票、GitHub Issue 与 PR 分别标注。

### Version progress

Milestone requirements and completion evidence live under `docs/versions/`. Update the current version's `completion.md` before starting the next milestone. See `docs/principles/04-cross-team-delivery.md`.

### Domain docs

Single-context: one `CONTEXT.md` plus `docs/adr/` at the repo root. See `docs/agents/domain.md`.
