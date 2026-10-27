# AI Banking Agent

为银发人群打造的银行智能助理：用自然语言理解金融意图，协助完成转账、账单分析与跨场景任务，并在敏感操作前要求用户确认。

> FinTechathon 2026 第八届深圳国际金融科技大赛 · 国内人工智能赛道（作品提交截止 2026-11-02）

## 当前进度

截至 2026-10-27，v0.3、v0.4 已收口（含明示例外），v0.5 仍进行中。转账、账单、订阅及三个生活目标的编排代码已合入；新版对话前台三票 #318 → #319 → #320 已合入，代码基线 `443e9b10`。

- 本次合入后本地前端 14 文件、122 项检查通过，真实 API 与契约演示两种构建通过；远端 CI 因账号计费未启动，不记为通过。
- 最新真实页面已验证账单与退订等所列路径；转账仍有风险事实覆盖暂停，生日只验到方案核对。三主线完整 E2E、200%/读屏/真机及最终安全/体验接受未完成，比赛材料仍待收口。
- 阶段目标与证据见[版本进度](docs/README.md)、[v0.5 完成情况](docs/versions/v0.5.0/completion.md)和[本次合入与剩余清单](.scratch/v05-control/frontend-merge-2026-10-27.md)；负责人和排期见[项目跟踪](docs/01-项目跟踪.md)。

## 三条铁律

1. **模型只负责理解和建议**：真正的执行权由确定的程序控制。
2. **动钱先确认**：敏感操作须暂停，等用户明确确认后沿原任务继续。
3. **银行结果说了算**：余额、限额和风控规则只在模拟银行，助理不自行判定交易成功。

## 项目目录

| 目录 | 内容 |
|---|---|
| [`backend/`](backend/README.md) | Python 后端；FastAPI、Pydantic、Deep Agents / LangGraph |
| [`frontend/`](frontend/README.md) | React 对话前台；账单、退订与生活安排等复用同一办理界面，真实业务验收按路径记录 |
| [`evals/`](evals/README.md) | 按业务和安全范围组织的评测集 |
| [`docs/`](docs/README.md) | 项目文档的事实来源，包括[文档索引](docs/00-项目文档索引.md)、[架构](docs/architecture/system-framework-2026-09-19.md)和[公共契约](docs/contracts/公共契约-2026-09-23.md) |
| `tools/` | 飞书同步等文档工具 |
| `官方资料/` | 大赛规则与提交要求 |

## 本地运行与协作

需要 Python 3.11 或更新版本。后端的安装、测试和启动命令见[后端说明](backend/README.md)，前端本地运行见 [frontend/LOCAL-DEV.md](frontend/LOCAL-DEV.md)。

开发分工与安全边界见 [AGENTS.md](AGENTS.md)，提交规则见[Git 与提交约定](docs/agents/git-workflow.md)。
