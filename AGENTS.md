# AGENTS.md

AI Banking Agent：为银发人群打造的银行智能助理，用自然语言理解金融意图并代理执行转账、账单、跨场景联动等业务，配权限分级、敏感确认与注入防御。

架构真相源：[docs/architecture/system-framework-v0.5.md](docs/architecture/system-framework-v0.5.md)。技术栈：Python 后端（FastAPI + Pydantic + Deep Agents/LangGraph），前端 Vue3。

## 目录边界

一次只负责一个目录，改动只落在你被分配的目录内：

| 目录 | 归属 |
|---|---|
| `backend/app/contracts/` `api/` `agent_platform/` | 底座（Erwin） |
| `backend/app/security/` `memory/` | 安全（Ringo） |
| `backend/app/modules/transfer/` | 转账（梁爽） |
| `backend/app/modules/bills/` | 账单（六水） |
| `backend/app/modules/cross/` | 联动（周恩宇） |
| `backend/app/services/` `storage/` | 底座共享 |
| 前端 / 适老化 | 待指定 |

## 开工先读

- 任何提交与分支操作 → [Git 与提交约定](docs/agents/git-workflow.md)
- 写或改业务模块 → [业务并行原则](docs/principles/01-business-parallel.md)
- 写或改安全底座 / 执行器 / 审计 → [安全底座原则](docs/principles/02-security-platform.md)
- 开分支、提 PR、审查合并 → [Review 与合并原则](docs/principles/03-review-and-merge.md)

## 三条铁律

1. **LLM 只动嘴不动手**：模型只理解、规划、回复；执行权在确定性代码手里。
2. **动钱必过确认门**：敏感操作暂停 → 前端确认 → 沿原任务继续。
3. **银行规则只在模拟银行**：结果只认银行返回，不复刻余额、限额、风控规则。

## 提交前自查

- 工具已声明权限、副作用、确认策略。
- 测试覆盖：正常、关键分支、暂停恢复、权限拒绝、异常兜底。
- 引用公共契约，不复制一份。
- PR 说明：场景编号、依赖、是否触及安全或契约。

## Agent skills

### Issue tracker

Issues and specs live as markdown files under `.scratch/`. See `docs/agents/issue-tracker.md`.

### Domain docs

Single-context: one `CONTEXT.md` plus `docs/adr/` at the repo root. See `docs/agents/domain.md`.
