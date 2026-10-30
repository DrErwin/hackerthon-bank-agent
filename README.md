# AI Banking Agent

## 1. 项目简介

- 参赛赛道：FinTechathon 2026 第八届深圳国际金融科技大赛 · 国内赛道·人工智能赛道（AI Banking Agent）
- 队伍名称：【待填：队伍名】
- 项目名称：【待填：作品名】
- 一句话介绍：给老年人用的银行智能助理。用户像聊天一样说出需求，Agent 听懂口语和改口、选对要办的业务；程序把它排成一步步能核对的任务，在“确认单 + 验证码/刷脸”之后代为办理转账、退订、生日和养老金安排。Agent 负责灵活理解，程序负责兜住安全。

已做的场景：01 转账、02 账单、05 订阅/代扣、06 跨场景联动（生日、养老金、减支）。03 理财、04 卡片，以及转账里的定时转账、AA 收款没有做，见[测试 · 已知限制](#已知限制)。

## 2. 系统架构

![系统架构图](docs/report/images/architecture.png)

用户在手机页面和 Agent 聊天，也可以直接在卡片上修改、确认、取消。请求依次经过后端服务入口、Agent 平台、业务模块、银行接入层，最后到模拟银行。Agent 平台用 LangChain 生态：Deep Agents 做 Agent 底座，LangGraph 提供状态、检查点、暂停与恢复，让银行业务能停下来等用户确认、中断后从原位置继续（转账是完整的 LangGraph 流程图，其余模块把状态存进同一套检查点）。模型 GLM-5.3 只负责听懂和用白话解释，它只能从白名单能力里选一项提议，步骤由程序排出，参数由程序校验；动钱的步骤一定会暂停，等本人在确认单上确认并通过验证后，才沿原任务继续。余额、限额、风控和去重只在模拟银行里判断，结果只认银行返回。完整设计见[系统框架](docs/architecture/system-framework-2026-09-19.md)和[公共契约](docs/contracts/公共契约-2026-09-23.md)。

| 模块 | 位置 | 作用 |
|---|---|---|
| 用户前端 | [`frontend/`](frontend/README.md) | React 聊天页面，计划卡、确认单、验证码框、进度、回执、恢复卡；`/admin` 是管理员演示页（模拟刷脸、时间线、重置） |
| 后端服务入口 | [`backend/app/api/`](backend/app/api/README.md) | FastAPI；演示登录、会话、任务与卡片动作接口、管理员接口 |
| Agent 平台 | [`backend/app/agent_platform/`](backend/app/agent_platform/README.md) | Deep Agents + LangGraph；理解意图、选能力、暂停与恢复；接 GLM-5.3 |
| 业务模块 | [`backend/app/modules/`](backend/app/modules/README.md) | 转账 `transfer`、账单 `bills`、订阅/代扣 `subscription`、跨场景联动 `cross` |
| 安全 | [`backend/app/security/`](backend/app/security/README.md) | 工具权限、确认门、验证、风险判断、外部文字按不可信数据处理 |
| 银行接入层与模拟银行 | [`backend/app/services/`](backend/app/services/README.md) | 统一银行接口；模拟银行负责账户、账本、规则、去重、模拟验证码/刷脸、演示重置 |
| 数据与运行记录 | `backend/app/storage/`、`backend/app/audit/`、`backend/app/memory/` | SQLite 保存任务、检查点、记忆、审计；银行数据单独存放 |
| 公共契约 | [`backend/app/contracts/`](backend/app/contracts/README.md) | 前后端与模块之间共用的 Pydantic 数据结构 |
| 评测集 | [`evals/`](evals/README.md) | 按转账、账单、订阅、联动、安全、模拟银行分目录的评测用例与运行记录 |

## 3. 环境与依赖

- 操作系统：Windows 10/11（下面命令以 PowerShell 为准，已在 Windows 11 实测）。macOS / Linux 未实测，可按[后端说明](backend/README.md)把 `.venv\Scripts\python` 换成 `.venv/bin/python`；`tools/start_local_dev.ps1` 只支持 Windows。
- 运行时版本：Python 3.11 或更新（实测 3.12.3）；Node.js 22.22+ 或 24.15+（实测 24.15.0，由 vitest 5 和 jsdom 30 的要求决定）；npm 随 Node 安装（实测 11.12.1）；Git。
- 主要依赖（后端版本锁在 [`backend/pyproject.toml`](backend/pyproject.toml)，前端锁在 [`frontend/package-lock.json`](frontend/package-lock.json)）：

| 端 | 依赖 | 版本 |
|---|---|---|
| 后端 | deepagents | 0.7.19 |
| 后端 | langgraph | 1.2.12 |
| 后端 | langchain-openai（连接智谱兼容接口） | 1.6.6 |
| 后端 | fastapi / uvicorn | 0.141.1 / 0.54.0 |
| 后端 | pydantic | 2.13.5 |
| 后端 | pytest（测试） | 9.1.1 |
| 前端 | react / react-dom | 19.3.0 |
| 前端 | vite / typescript | 8.3.1 / 7.0.2 |
| 前端 | tailwindcss / radix-ui | 4.3.3 / 1.8.1 |
| 前端 | vitest / jsdom（测试） | 5.0.3 / 30.1.1 |

- 模型：GLM-5.3，走智谱 Coding Plan 接口 `https://open.bigmodel.cn/api/coding/paas/v4/`，用兼容 OpenAI 的接口调用（客户端是 langchain-openai，但请求发给智谱，不是 OpenAI）。需要自己的智谱密钥。

### 环境变量与本机配置

请勿提交真实密钥或敏感信息。密钥只放在本机配置文件 `.env.local-demo.json` 里，它已被 `.gitignore` 的 `.env.*` 忽略；前端不保存任何密钥。

后端环境变量：

| 变量 | 用途 |
|---|---|
| `BANK_LOCAL_CONFIG` | 必填。本机配置文件 `.env.local-demo.json` 的绝对路径 |
| `BANK_PENSION_DEMO_PROFILE` | 选填。只在养老金演示时设为 `p01-marked-demo-v1`，默认不开 |
| `PYTHONPATH` | 只在运行 `evals/cross/case_runner.py`（养老金演示）时需要，指向仓库的 `backend/` |

本机配置文件 `.env.local-demo.json` 的键（模板：[`local_demo.example.json`](backend/app/agent_platform/local_demo.example.json)）：

| 键 | 用途 |
|---|---|
| `api_key` | 智谱模型密钥 |
| `api_secret` | 会话签名用的固定随机串，至少 32 字节 |
| `bank_secret` | 模拟银行验证码用的固定随机串，至少 32 字节 |
| `admin_key` | 管理员页登录口令，随机生成 |
| `model_name` | 模型名，演示用 `glm-5.3` |
| `base_url` | 模型接口地址，演示用 Coding Plan 地址（模板里没有这一项，要自己加） |
| `data_directory` | 本机数据目录，必须是绝对路径；任务、审计和银行库都存在这里 |
| `facts_version`、`read_fixture`、`transfer_fixtures` | 演示用的虚构风险事实（500/501/502/600 元等场景），照模板保留即可 |
| `birthday_response_loss_once` | 生日“银行响应丢失一次”的故障演示开关，默认 `false` |

前端变量（模板：[`frontend/.env.example`](frontend/.env.example)）：

| 变量 | 用途 |
|---|---|
| `VITE_API_MODE` | `real-api` 连真实后端；`contract-demo` 只用浏览器里的固定演示数据，不连后端 |
| `VITE_API_PROXY_TARGET` | 后端地址，默认 `http://127.0.0.1:8000` |

## 4. 安装与运行

以下步骤已在全新目录实测（2026-10-30，Windows 11）。后端依赖第一次下载约 3 分钟，前端约 15 秒。

### 4.1 获取代码

```powershell
git clone https://github.com/DrErwin/hackerthon-bank-agent.git
cd hackerthon-bank-agent
```

### 4.2 后端：虚拟环境与依赖

```powershell
python -m venv backend/.venv
backend/.venv/Scripts/python -m pip install -e 'backend[dev]'
```

`[dev]` 会一起装上 pytest；只运行、不测试时可以改成 `-e backend`。

### 4.3 前端依赖

```powershell
cd frontend
npm ci
Copy-Item .env.example .env
cd ..
```

`.env` 默认就是 `real-api`、代理到 `http://127.0.0.1:8000`，不用改。

### 4.4 配置模型密钥

```powershell
Copy-Item backend/app/agent_platform/local_demo.example.json .env.local-demo.json
```

用编辑器打开 `.env.local-demo.json`：

1. `api_key` 填自己的智谱密钥。
2. `api_secret`、`bank_secret`、`admin_key` 各填一个不同的随机串（至少 32 个字符）。可以用 `python -c "import secrets; print(secrets.token_hex(32))"` 生成。以后重启沿用同一组值。
3. `model_name` 改成 `glm-5.3`，并加一行 `"base_url": "https://open.bigmodel.cn/api/coding/paas/v4/"`。
4. `data_directory` 改成本机的绝对路径，例如 `D:/bank-agent-demo-data`。

只想看安装和测试、不调用模型时，`api_key` 填任意非空占位值也能启动，只是聊天会失败。

### 4.5 启动后端和前端

终端 1（仓库根目录）：

```powershell
$env:BANK_LOCAL_CONFIG = (Resolve-Path .env.local-demo.json).Path
cd backend
.venv\Scripts\python -m uvicorn app.agent_platform.local_demo:create_local_app --factory --host 127.0.0.1 --port 8000 --workers 1 --no-access-log
```

看到 `Application startup complete` 即就绪。

终端 2（仓库根目录）：

```powershell
cd frontend
npm run dev
```

Windows 上也可以在仓库根目录用一个命令同时拉起两者：`pwsh tools/start_local_dev.ps1`（按任意键停止；这个脚本不在 2026-10-30 全新环境实测范围内）。

### 4.6 浏览器访问

| 页面 | 地址 | 说明 |
|---|---|---|
| 用户页 | `http://127.0.0.1:5173/` | 自动以演示用户登录。建议用手机宽度（如 390×844）查看 |
| 管理员页 | `http://localhost:5173/admin` | 注意是 `localhost`，和用户页用不同的主机名，两边会话分开 |

可以试的话：“给妈妈转500元”（低风险：确认单 + 验证码）、“给妈妈转501元”（中风险：再加模拟刷脸）、“给妈妈转502元”（高风险：直接终止，不动钱）、“帮我减少不用的开销”、“看看这个月花了多少”。模型每一步可能要等 1—5 分钟。

### 4.7 管理员页：模拟刷脸

1. 用户页遇到“等工作人员处理”的刷脸等待卡时，点卡上的“演示用：管理员入口”，会在新标签页打开 `http://localhost:5173/admin`，并带上任务编号和验证编号。
2. 第一次进入时输入 `.env.local-demo.json` 里的 `admin_key`。
3. 在“模拟人脸核验”里点“模拟通过”或“模拟未通过”。回到用户页，卡片会自动更新。

这不是真实人脸识别，只是让管理员代替刷脸给出结果。管理员页还能读取任务的脱敏运行时间线。

### 4.8 重置演示数据

在管理员页的“演示整体重置”里，依次点“查看重置影响” → 勾选“我已核对以上影响，确认重置本轮演示” → “确认并重置本轮演示”。看到“重置已全部完成”后回到用户页重新进入。模拟银行回到初始余额，旧会话和旧按钮失效，历史记录保留供查阅。

想完全从头开始，也可以停掉后端，把 `data_directory` 改成一个新的空目录再启动。

### 4.9 养老金演示（可选）

养老金场景要用单独的一套隔离数据：账户里只有本月到账的 5000 元养老金（普通启动还会多一笔工资，金额对不上）。另外要显式开启已批准的演示设定 `p01-marked-demo-v1`。它的端口和数据与 4.5 分开：

终端 1（仓库根目录，只需第一次 `prepare`）：

```powershell
$env:PYTHONPATH = (Resolve-Path backend).Path
backend\.venv\Scripts\python evals/cross/case_runner.py prepare XL-P01 --config .env.local-demo.json --run-id p01-demo
$env:BANK_PENSION_DEMO_PROFILE = 'p01-marked-demo-v1'
backend\.venv\Scripts\python evals/cross/case_runner.py serve --directory .mnemon/v05-cross-e2e/XL-P01/p01-demo --port 8165
```

终端 2：

```powershell
cd frontend
$env:VITE_API_PROXY_TARGET = 'http://127.0.0.1:8165'
npm run dev -- --port 5265
```

打开 `http://127.0.0.1:5265/`（管理员页 `http://localhost:5265/admin`）。第一句必须逐字发送下面这句批准原话，不能改字、不能加话：

> 这月养老金5000元到账了，帮我安排一下：留1500元生活费，2500元转自己的储蓄账户，1000元给家人，顺便看看没用的扣费。

之后只点卡片选项；卡片要求填写时，只输入“1500元”“2500元”“1000元”。首句不是原话时，转账会被安全核对暂停，钱不会动。`prepare` 每次要用新的 `--run-id`，重新演示时换一个名字即可。

## 5. 测试

### 5.1 测试命令

后端（在 `backend/` 目录）：

```powershell
.venv\Scripts\python -m pytest -q                        # 全量，耗时较长
.venv\Scripts\python -m pytest -q app/modules/transfer   # 只跑转账模块，约 40 秒
.venv\Scripts\python -m pytest -q ../evals/mockbank/test_mockbank_eval.py   # 模拟银行评测
```

前端（在 `frontend/` 目录）：

```powershell
npm test         # 组件与交互测试（vitest + jsdom）
npm run build    # TypeScript 检查 + 生产构建
```

### 5.2 用例位置

- 后端单元与集成测试：和代码放在一起，文件名 `test_*.py`，例如 [`backend/app/modules/transfer/`](backend/app/modules/transfer/)、[`backend/app/security/`](backend/app/security/)、[`backend/app/agent_platform/`](backend/app/agent_platform/)；工程入口测试在 [`backend/tests/`](backend/tests/)。
- 前端测试：[`frontend/src/`](frontend/src/) 下的 `*.test.ts(x)`，共 15 个文件，覆盖转账确认、验证码、模拟刷脸、恢复、生日与联动卡片、管理员重置等。
- 评测集：[`evals/`](evals/README.md)，按 [转账](evals/transfer/cases.md)、[账单](evals/bills/README.md)、[订阅](evals/subscription/cases.md)、[联动](evals/cross/README.md)、[安全](evals/security/README.md)、[模拟银行](evals/mockbank/README.md) 分目录。

### 5.3 预期结果

以下为 2026-10-30 本地结果，分层列出，不相加成一个“总通过率”。

| 层次 | 结果 |
|---|---|
| 前端 `npm test` | 136/136 通过；`npm run build` 通过 |
| 后端全量 `pytest` | 2621 passed / 5 failed / 13 skipped。5 个失败在改动前的主线 `68219a2a` 上同样失败，是与风险暂停有关的旧断言 |
| 全新环境实测（2026-10-30） | 从 clone 开始安装成功；前端 136/136、构建通过；`app/modules/transfer` 82 passed；后端、前端、管理员会话、演示重置、养老金案例都能启动 |
| 远端 CI | 因 GitHub 账号计费未启动，未运行 |

历史评测（带日期和来源）：转账评测 153/153 Passed（v0.3，2026-10-11）；账单 L01/L02/L03 实跑 20/30/22 条（v0.4）；安全 96 条独立分类中 86/96 与参考标签一致（这是分类一致率，不是拦截率）；B 批 12 个攻击轮 3 Failed / 9 Blocked；C 批 6 条全部 Blocked。汇总见[报告事实与证据入口](docs/versions/v1.0.0/report-evidence-2026-10-29.md)。

### 已知限制

- 后端全量有 5 个旧失败（见上表）；订阅评测有 5 条（SUB-CAN-01/14/19、GUD-01、eval_22）在主线上同样失败。
- 模型慢：卡片之间常要等 1—5 分钟，偶尔超时或被限流；超时后可以在恢复卡上“继续办理”。
- 模拟银行不是真实银行；刷脸是管理员页模拟作答，不是真实生物识别；部分风险判断用的是预设的虚构演示场景（页面顶栏有说明），没有配置的转账会暂停而不是放行。
- 养老金演示只在显式开启 `p01-marked-demo-v1` 且首句为批准原话时能办完，不是通用的养老金识别。
- 没做：03 理财、04 卡片、定时转账、AA 收款；语音按钮只是固定文字示例，不采集声音。
- 未测：真实 200% 浏览器缩放、完整读屏、真机。
- 前端生产构建有一条“单个文件大于 500 kB”的提示，不影响运行。

## 6. 仓库与部署

- GitHub / Git 仓库地址：https://github.com/DrErwin/hackerthon-bank-agent
- 在线演示地址（如有）：无
- 部署说明：只支持本机运行，按第 4 节启动。后端须单进程（`--workers 1`）；配置只允许本机浏览器来源（`127.0.0.1`/`localhost`）。没有做公网或生产部署。

## 7. 安全说明

按风险分级处理：查询类直接办理；动钱的操作一律暂停，出确认单，由本人在卡片上确认，再按风险输入验证码，中风险还要模拟刷脸，之后才沿原任务提交；高风险直接终止。模型只能从白名单能力里选，参数由程序校验，权限由服务端判定，前端不做权限判断。验证码只能填在卡片专用框里，发进聊天会被拦下；工具返回和外部文字（例如可疑短信）按不可信数据处理，不能变成指令。演示数据全部是虚构的，密钥只放在本机配置里，审计记录脱敏。安全审查由团队内部完成（PM 代行），未经第三方签核；已知风险包括生产环境下的未知风险维度尚未收口、部分风险判断依赖预设演示场景。详见[安全自评](docs/report/02-安全自评.md)。

## 团队协作文档

### 三条铁律

1. **LLM 只动嘴不动手**：模型只理解、规划、回复；真正的执行权由确定的程序控制。
2. **动钱必过确认门**：敏感操作须暂停，等用户明确确认后沿原任务继续。
3. **银行规则只在模拟银行**：余额、限额和风控规则只在模拟银行，结果只认银行返回，助理不自行判定交易成功。

### 项目目录

| 目录 | 内容 |
|---|---|
| [`backend/`](backend/README.md) | Python 后端；FastAPI、Pydantic、Deep Agents / LangGraph |
| [`frontend/`](frontend/README.md) | React 对话前台；账单、退订与生活安排等复用同一办理界面 |
| [`evals/`](evals/README.md) | 按业务和安全范围组织的评测集 |
| [`docs/`](docs/README.md) | 项目文档的事实来源，包括[文档索引](docs/00-项目文档索引.md)、[架构](docs/architecture/system-framework-2026-09-19.md)和[公共契约](docs/contracts/公共契约-2026-09-23.md) |
| `tools/` | 一键启动脚本、飞书同步等工具 |
| `官方资料/` | 大赛规则与提交要求 |

### 内部文档

- 进度：[版本进度](docs/README.md)、[v0.5 完成情况](docs/versions/v0.5.0/completion.md)、[项目跟踪](docs/01-项目跟踪.md)
- 报告取证：[报告事实与证据入口](docs/versions/v1.0.0/report-evidence-2026-10-29.md)
- 更细的本机运行说明：[后端说明](backend/README.md)、[本机 GLM 运行组合](backend/app/agent_platform/LOCAL-DEV.md)、[前端本机说明](frontend/LOCAL-DEV.md)、[联动案例数据](evals/cross/fixture-runbook.md)
- 分工与安全边界：[AGENTS.md](AGENTS.md)；提交规则：[Git 与提交约定](docs/agents/git-workflow.md)
