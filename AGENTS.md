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
| `backend/app/modules/subscription/` | 订阅 / 代扣（Erwin；2026-10-19 起） |
| `backend/app/modules/cross/` | 联动（周恩宇） |
| `backend/app/services/` `storage/` | 底座共享 |
| `frontend/` | 前端 / 适老化（梁爽负责，六水协助；2026-09-25 确认） |
| `evals/` | 评测集，按子目录归属：transfer Erwin · bills 周恩宇 · subscription Erwin · cross 周恩宇 · security Ringo · mockbank Erwin（2026-09-28 全员会调整；2026-10-19 增 subscription） |

### 版本执行状态（2026-10-19 更新）

v0.3 已于 2026-10-11 收口（含明示例外）；v0.4 同日启动：账单 + 完整安全 + 完整前端（转账+账单双场景，目标 10-20），2026-10-19 新增场景 05 订阅 / 代扣管理（Erwin 负责，`v04-subscription`），联动移至 v0.5。各线交付包、开始条件与领取状态的正式入口是[项目跟踪](docs/01-项目跟踪.md)。v0.3 期间的临时分工（Erwin 代行底座/最小安全门/转账参考路径/简易前端等）已随收口结束，目录归属回归上表。

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

`docs/` 是唯一事实源，飞书是阅读端，方向只出不回。同步由人决定何时执行：

```bash
python tools/feishu_sync.py plan      # 只看会推哪些文档，不碰飞书
python tools/feishu_sync.py publish   # 推内容：缺失的新建、已存在的原地覆盖
python tools/feishu_sync.py mount     # 把还没进知识库的挂进对应分区（幂等）
```

白名单三层、标题固定（`TITLE_OVERRIDES`）、同步工作台后重建甘特图（`embed_stages.py`）与用户身份授权注意事项，见[Git 与提交约定 §4 飞书同步](docs/agents/git-workflow.md#4-飞书同步)。

## Agent skills

### Issue tracker

规格与实施票放在 `.scratch/`。新建、引用或领取票据时先读[票据标识规范](docs/agents/issue-tracker.md)：组内分别编号，对外使用完整票号 `<feature-slug>/<NN>`、标题及链接；交付包、实施票、GitHub Issue 与 PR 分别标注。**GitHub Issue 建单时必须写明转给谁**（正文 `转给: <姓名>`；有权限时一并设置 Assignee），没有明确接收人不建单。

### Version progress

Milestone requirements and completion evidence live under `docs/versions/`. Update the current version's `completion.md` before starting the next milestone. See `docs/principles/04-cross-team-delivery.md`.

### Domain docs

Single-context: one `CONTEXT.md` plus `docs/adr/` at the repo root. See `docs/agents/domain.md`.


## 纯文档改动的检查与合并（2026-10-04）

用户明确要求：**“以后纯文档改动就不要CI了”以及“纯文档的提交不用PR”。**

- 纯文档可在核对最新main后直接提交并推送主线，不创建PR；本条优先于旧的全量PR约定。
- 纯文档改动（README、AGENTS、规格与票据、用例说明、进度及其他说明文档）只做必要的内容核对、链接/锚点、格式、编号和差异空白检查。
- 不主动运行 CI，不跑后端/前端全量回归；不等待 CI，也不把 CI 作为纯文档 PR 的合并门槛。只有用户对本次文档变更明确要求时才运行 CI。
- GitHub Actions已通过[PR #49](https://github.com/DrErwin/hackerthon-bank-agent/pull/49)启用路径过滤（提交`fd6c677`）：Markdown/reST以及docs目录内的mmd/png/jpg/jpeg/svg/pdf图示全部匹配时，PR和main推送不创建Repository checks运行；混入任一代码、依赖或执行配置仍触发。其他文档格式按现有过滤结果处理，不把自动触发作为纯文档合并等待理由。
- 涉及运行代码、依赖、构建、部署或 CI 执行配置的变更，仍按影响范围做必要测试及 CI；不能按纯文档处理。
- 开工先判断改动类型，按本条选择检查，不再对纯文档改动重复要求 CI。
