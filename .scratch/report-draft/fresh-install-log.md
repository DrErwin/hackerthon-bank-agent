# 全新环境安装实测记录（2026-10-30）

目的：按根目录 README“安装与运行”的步骤，从空目录 clone 开始，验证能装好、测试能跑、构建通过、服务能启动。不配置真实模型密钥，不做真实模型对话。

## 环境

- 机器：Windows 11（NT 10.0.26200），PowerShell 7
- Python 3.12.3（系统已装）；Node.js v24.15.0；npm 11.12.1
- 测试目录：`D:\hb-fresh-install-test\hackerthon-bank-agent`（结束后已删除）
- 代码：`git clone D:\hackerthon-bank-agent` 后 `git checkout --detach 4269e005`（即当时 origin/main，#359）
- 主仓库 `D:\hackerthon-bank-agent` 的 `.venv`、`node_modules` 未使用、未改动；npm 用独立缓存目录 `--cache D:\hb-fresh-install-test\npm-cache`，pip 用 `--no-cache-dir`，确保依赖真实从网络下载

## 逐步结果

| # | 步骤 | 命令（在仓库根目录，另注明除外） | 耗时 | 结果 | 输出摘要 |
|---|---|---|---|---|---|
| 1 | 克隆并切到指定提交 | `git clone D:\hackerthon-bank-agent ...`；`git checkout --detach 4269e005` | 3.4 s | 成功 | 1936 个文件；`git status` 干净 |
| 2 | 新建后端虚拟环境 | `python -m venv backend/.venv` | 13.7 s | 成功 | venv 自带 pip 24.0（提示可升级到 26.2.2，不影响） |
| 3 | 安装后端依赖（含测试） | `backend/.venv/Scripts/python -m pip install --no-cache-dir -e 'backend[dev]'` | 188.7 s | 成功 | 共装 71 个包，关键版本：deepagents 0.7.19、fastapi 0.141.1、langgraph 1.2.12、langchain-openai 1.6.6、langchain-core 1.7.3、pydantic 2.13.5、uvicorn 0.54.0、pytest 9.1.1。无网络报错 |
| 4 | 安装前端依赖 | `npm ci`（在 `frontend/`） | 15.7 s | 成功 | `added 201 packages`；仅有 npm 新版本提示 |
| 5 | 前端测试 | `npm test`（在 `frontend/`） | 16.7 s | 成功 | `Test Files 15 passed (15)`，`Tests 136 passed (136)` |
| 6 | 前端生产构建 | `npm run build`（在 `frontend/`） | 3.8 s | 成功 | `tsc -b && vite build`，2088 modules，`built in 865ms`；有一条“chunk 大于 500 kB”的提示（`index-*.js` 565.58 kB），是警告不是错误 |
| 7 | 后端快速测试 | `.venv\Scripts\python -m pytest -q app/modules/transfer`（在 `backend/`） | 41.5 s | 成功 | `82 passed in 37.99s` |
| 8 | 复制并填写本机配置（占位值） | `Copy-Item backend/app/agent_platform/local_demo.example.json .env.local-demo.json`，填占位 `api_key`、随机生成 3 个 64 位秘密、`model_name=glm-5.3`、`base_url=https://open.bigmodel.cn/api/coding/paas/v4/`、`data_directory` 为绝对路径 | <1 s | 成功 | `git status --ignored` 显示该文件为 `!!`（已被 `.gitignore` 的 `.env.*` 忽略，不会误提交） |
| 9 | 启动后端（演示组合） | `$env:BANK_LOCAL_CONFIG=(Resolve-Path .env.local-demo.json).Path`；在 `backend/` 运行 `.venv\Scripts\python -m uvicorn app.agent_platform.local_demo:create_local_app --factory --host 127.0.0.1 --port 8000 --workers 1 --no-access-log` | 约 5 s 就绪 | 成功 | `Application startup complete`；`GET /api/v1/session` 未登录返回 401 `AUTH_REQUIRED`（符合预期） |
| 10 | 启动前端 | 在 `frontend/`：`Copy-Item .env.example .env`；`npm run dev` | 约 3 s 就绪 | 成功 | `http://127.0.0.1:5173/` 与 `http://127.0.0.1:5173/admin` 均 200 |
| 11 | 经前端代理建立演示会话 | `POST http://127.0.0.1:5173/api/v1/session/enter` | — | 成功 | 200，`role=user`、`demo_round_id=D1`；随后 `GET /api/v1/threads` 200（空列表） |
| 12 | 管理员会话 | `POST http://localhost:5173/api/v1/session/enter`，头 `X-Demo-Admin-Key` 为配置里的 `admin_key` | — | 成功 | 200，`role=admin` |
| 13 | 演示数据整体重置（接口） | 管理员会话下 `POST /api/v1/admin/demo/reset-preview` → `POST /api/v1/admin/demo/reset` | — | 成功 | 预览 200；重置 200，`status=succeeded`、`phase=completed` |
| 14 | 准备养老金隔离案例 | `$env:PYTHONPATH=<仓库>\backend`；`backend\.venv\Scripts\python evals/cross/case_runner.py prepare XL-P01 --config .env.local-demo.json --run-id p01-fresh` | 6.3 s | 成功 | 输出 `bank_seed: prepared`；案例目录在 `.mnemon/v05-cross-e2e/XL-P01/p01-fresh` |
| 15 | 启动养老金案例后端 | 同上 `PYTHONPATH`，另设 `$env:BANK_PENSION_DEMO_PROFILE='p01-marked-demo-v1'`；`... case_runner.py serve --directory .mnemon/v05-cross-e2e/XL-P01/p01-fresh --port 8165` | 约 5 s 就绪 | 成功 | `Uvicorn running on http://127.0.0.1:8165` |
| 16 | 养老金案例前端 | 在 `frontend/`：`$env:VITE_API_PROXY_TARGET='http://127.0.0.1:8165'`；`npm run dev -- --port 5265` | 约 3 s | 成功 | 页面 200；经 5265 代理 `session/enter` 200，`role=user` |
| 17 | 检查后端 README 原启动命令 | 在 `backend/`：`.venv\Scripts\python -m uvicorn app.api.app:app --port 8001` | 5.5 s | 失败（文档问题） | 进程退出码 3：`RuntimeError: Set BANK_RUNTIME_FACTORY=module:function to a trusted TransferRuntime factory`，`Application startup failed` |
| 18 | 清理 | 停止全部后台服务；确认路径后删除 `D:\hb-fresh-install-test` | — | 成功 | 见文末 |

未做：真实模型对话（没有配置真实密钥）、浏览器里点完整业务、后端全量测试、`evals/` 评测、`tools/start_local_dev.ps1` 一键脚本（它要开新窗口并等按键，本次分别手动启动后端和前端）、4.5 与 4.9 两套服务同时运行。

## 发现的文档问题（已在根 README 按实测修正）

1. `backend/README.md` 的“本地启动”写 `uvicorn app.api.app:app --reload`，全新环境直接运行会启动失败（第 17 步）：该入口要求先设置 `BANK_RUNTIME_FACTORY` 等变量，而仓库里没有现成的工厂说明给评委用。能用的入口是 `app.agent_platform.local_demo:create_local_app --factory`（第 9 步），根 README 只写这一种。
2. 根目录旧 README 指向 `frontend/LOCAL-DEV.md`，那里第一步写 `npm install`；有 `package-lock.json` 时应写 `npm ci`，才能装出和锁文件一致的版本。
3. `local_demo.example.json` 默认 `model_name=glm-4.7`、不含 `base_url`；比赛演示用 GLM-5.3（Coding Plan），需要手动加 `base_url=https://open.bigmodel.cn/api/coding/paas/v4/` 并把 `model_name` 改成 `glm-5.3`。旧文档只在长段落里提到。
4. 没有任何文档说明 Node.js 版本要求。按锁文件，vitest 5.0.3 要求 Node `^22.12.0 || ^24.0.0 || >=26`，jsdom 30.1.1 要求 `^22.22.2 || ^24.15.0 || >=26`；实测用的是 v24.15.0。
5. 养老金演示的启动方式分散在 `backend/app/agent_platform/LOCAL-DEV.md`（环境变量）和 `evals/cross/fixture-runbook.md`（必须用 `case_runner.py`，否则普通启动会多播一笔 6200 元工资，到账金额对不上），且后者写的是团队机器的固定路径 `D:\hackerthon-bank-agent\backend\.venv`。根 README 已合并成一段可复制的步骤。
6. `tools/start_local_dev.ps1` 最后的提示仍写“账单仍在开发中（v0.4），联动已移至 v0.5”，已过时。脚本属于代码范围，本次没有改，只记录。
7. `docs/report/images/architecture.png` 与 `docs/report/02-安全自评.md` 在本工作树里还不存在（同事在做），README 已先按固定路径引用。

## 清理

- 停止了本次启动的 4 个后台服务（8000、5173、8165、5265），端口确认已释放。
- 删除前用 `Resolve-Path` 确认目标为 `D:\hb-fresh-install-test`，再执行删除；删除后 `Test-Path` 为 False。
- 临时日志 `uvicorn-plain.out/.err` 位于该目录内，一并删除。主仓库与本工作树的代码未改动。
