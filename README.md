# AI Banking Agent

为银发人群打造的银行智能助理：用自然语言理解金融意图，协助完成转账、账单分析与跨场景任务，并在敏感操作前要求用户确认。

> FinTechathon 2026 第八届深圳国际金融科技大赛 · 国内人工智能赛道（作品提交截止 2026-11-02）

## 当前进度

截至 2026-10-11，v0.3 普通转账纵向链路**已收口**（含明示例外）：用户可从简易 React 前端经真实 API 与 GLM 完成转账的确认、验证与结果闭环；转账评测 153/153，AF01—AF14 证据入库。

- v0.4 已于同日启动：账单 + 完整安全 + 完整前端（转账+账单双场景，目标 10-20）；联动移至 v0.5。
- 阶段目标与完成证据见[版本进度](docs/README.md)、[v0.3 完成情况](docs/versions/v0.3.0/completion.md)与[v0.4 完成情况](docs/versions/v0.4.0/completion.md)；负责人和排期见[项目跟踪](docs/01-项目跟踪.md)。

## 三条铁律

1. **模型只负责理解和建议**：真正的执行权由确定的程序控制。
2. **动钱先确认**：敏感操作须暂停，等用户明确确认后沿原任务继续。
3. **银行结果说了算**：余额、限额和风控规则只在模拟银行，助理不自行判定交易成功。

## 项目目录

| 目录 | 内容 |
|---|---|
| [`backend/`](backend/README.md) | Python 后端；FastAPI、Pydantic、Deep Agents / LangGraph |
| [`frontend/`](frontend/README.md) | React 前端；简易版已与真实 API 联调，完整版按 v0.4 交付包推进 |
| [`evals/`](evals/README.md) | 按业务和安全范围组织的评测集 |
| [`docs/`](docs/README.md) | 项目文档的事实来源，包括[文档索引](docs/00-项目文档索引.md)、[架构](docs/architecture/system-framework-2026-09-19.md)和[公共契约](docs/contracts/公共契约-2026-09-23.md) |
| `tools/` | 飞书同步等文档工具 |
| `官方资料/` | 大赛规则与提交要求 |

## 本地运行与协作

需要 Python 3.11 或更新版本。后端的安装、测试和启动命令见[后端说明](backend/README.md)，前端本地运行见 [frontend/LOCAL-DEV.md](frontend/LOCAL-DEV.md)。

开发分工与安全边界见 [AGENTS.md](AGENTS.md)，提交规则见[Git 与提交约定](docs/agents/git-workflow.md)。
