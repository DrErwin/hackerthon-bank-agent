# AGENTS.md

AI Banking Agent：为银发人群打造的银行智能助理，用自然语言理解金融意图并代理执行转账、账单、跨场景联动等业务，配权限分级、敏感确认与注入防御。

架构真相源：[docs/architecture/system-framework-2026-09-19.md](docs/architecture/system-framework-2026-09-19.md)。技术栈：Python 后端（FastAPI + Pydantic + Deep Agents/LangGraph），前端 Vue3。

## 目录边界

一次只负责一个目录，改动只落在你被分配的目录内：

| 目录 | 归属 |
|---|---|
| `backend/app/contracts/` `api/` `agent_platform/` | 底座（Erwin） |
| `backend/app/audit/` | 底座（Erwin）：运行日志写入与只读回放；审计规则由安全侧定 |
| `backend/app/security/` | 安全（Ringo）：策略、执行器、确认；审计与记忆的安全规则 |
| `backend/app/memory/` | 底座（Erwin）：Agent 长期记忆与上下文后端，随 harness 走；安全规则由安全侧定 |
| `backend/app/modules/transfer/` | 转账（梁爽） |
| `backend/app/modules/bills/` | 账单（六水） |
| `backend/app/modules/cross/` | 联动（周恩宇） |
| `backend/app/services/` `storage/` | 底座共享 |
| `frontend/` | 前端 / 适老化（梁爽负责，六水协助；2026-09-25 确认） |
| `evals/` | 评测集，按子目录归属：transfer 梁爽 · bills 六水 · cross 周恩宇 · security Ringo · mockbank Erwin |

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

## 飞书同步工具

`docs/` 是唯一事实源，飞书是阅读端，方向只出不回。同步由人决定何时执行，命令如下：

```bash
python tools/feishu_sync.py plan      # 只看会推哪些文档，不碰飞书
python tools/feishu_sync.py publish   # 推内容：缺失的新建、已存在的原地覆盖
python tools/feishu_sync.py mount     # 把还没进知识库的挂进对应分区（幂等）
```

范围自动扫描 `docs/`（外加 `官方资料/` 已发布的两份），新增文档不用改脚本；排除规则、标题与分区规则都在 `tools/feishu_publish_all.py`。三条都可重复跑。一条要知道的：**飞书按标题认文档**，已发布文档的标题固定在 `TITLE_OVERRIDES` 里——标题一变，飞书会新建一篇而不是更新它。

## Agent skills

### Issue tracker

Issues and specs live as markdown files under `.scratch/`. See `docs/agents/issue-tracker.md`.

### Domain docs

Single-context: one `CONTEXT.md` plus `docs/adr/` at the repo root. See `docs/agents/domain.md`.
