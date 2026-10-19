# 票 03 真实接口走查证据（2026-10-20）

- 票：[liangshuang-frontend-complete/03：完整转账业务插槽](https://github.com/DrErwin/hackerthon-bank-agent/blob/main/.scratch/liangshuang-frontend-complete/issues/03-transfer-slot.md)
- PR：[#142](https://github.com/DrErwin/hackerthon-bank-agent/pull/142) head `59dd9caf`；合入 main `92ee700`（2026-10-20 squash）
- 执行：AI 实施者（Lead 会话）代执行 · **AI 代填留痕**，非真人人工走查
- 本证据补齐票 03 Verification 项「真实接口可用后重跑同一路径」，同时关闭 PR 合并前的「真实接口路径从未跑过」硬门槛

## 1. 环境

| 项 | 值 |
|---|---|
| 前端 | PR head `59dd9caf` 独立 worktree（`C:\Users\57652\AppData\Local\Temp\rv4-142`），Vite dev `127.0.0.1:5173`，`VITE_API_MODE=real-api`，`VITE_API_PROXY_TARGET=http://127.0.0.1:8000` |
| 后端 | 仓库 main `399a2fe`（后端不属本票改动），`uvicorn app.agent_platform.local_demo:create_local_app --factory --port 8000`，配置 `.env.local-demo.json` |
| 模型 | 智谱 `glm-5.3`，**Coding Plan 入口** `https://open.bigmodel.cn/api/coding/paas/v4/`（普通 API 入口未切换） |
| 银行 | 模拟银行（受控组合，`U1` 演示用户 + 独立 `demo-admin`） |
| 浏览器 | Microsoft Edge（系统安装，headless），视口 1280×900 |
| 驱动 | `puppeteer-core`（`npm i --no-save`，不写入 `package.json`） |

## 2. 路径与结果

干净新线程（脚本先 `POST /threads` 建空线程并确认成为前端激活线程，避免演示数据里 2026-10-12 旧任务干扰）：

1. `/v04` 首屏：顶栏 `演示用户 · 已连接`，**无** contract-demo 标记 / demo ribbon → 真实数据源。
2. 发送「给妈妈转500元，主账户A1」→ GLM 返回正式确认单（转出账户 主账户 0001、金额 500.00 元、收款人 王\*\* \*\*\*\*0002、手续费 0.00 元、低风险提示）。
3. **点「确认办理」按钮**（未在聊天里说「确认」）→ 进入专用验证码步骤。
4. 演示提示区取码 → 填入专用验证码框 → 「提交验证码」→ **转账成功**。
   - 银行交易号：`2b2bd26e-894c-478e-b562-f2c885b826ba`（页面展示值 = 后端返回，非前端生成）
5. 整页刷新：确认单「已确认办理 · 只读」、验证「验证已通过 · 只读」、转账结果卡全部恢复；任务块内 **0 个可用按钮**、无「有一项没办完的任务」恢复门、无「正在读取确认单…」卡住占位。
6. **新浏览器上下文（新 Cookie / 新会话）**：用 F39 回放同一任务的只读确认单与验证记录，无可用按钮、无卡住占位 → 跨会话恢复路径成立。

## 3. 脚本断言（全部 PASS）

| 检查 | 结果 |
|---|---|
| `realApiNoDemoRibbon`：真实源，无演示回退标记 | PASS |
| `modelProducedPlan`：真实模型产出可操作确认单 | PASS |
| `confirmGateClicked`：确认门经后端按钮作答 | PASS |
| `codeVerificationPassed`：专用验证码通过、转账成功且交易号回填 | PASS |
| `refreshRestoredReadOnly`：刷新后只读恢复、无恢复门、无卡住占位 | PASS |
| `refreshNoLiveConfirm`：刷新后无可用确认按钮 | PASS |
| `crossSessionReadOnlyReplay`：跨会话 F39 回放只读、无卡住占位 | PASS |
| `crossSessionNoLiveConfirm`：跨会话无可用确认按钮 | PASS |
| `noUnexpectedApiFailures`：无预期外 API 失败 | PASS |

`verdict = PASS`。

## 4. API 观测

42 次 `/api/v1` 调用：36×200 / 1×202（发消息受理）/ 2×401（首次未登录 `GET /session`，随后 `POST /session/enter`，设计内）/ 3×409。

3 次 409 均为**旧会话历史记录**的逐条 `GET /confirmations|verifications/{id}` 返回 `SESSION_RECONFIRMATION_REQUIRED`（这些记录属 2026-10-12 的旧会话任务）；F39 `task_records` 视图已把只读内容直接渲染，页面无缺失、无卡住占位，**不影响本票验收**。建议 v0.5 对历史条目跳过逐条 F14/F16 刷新（或对 409 做静默降级），已记入票 03 Comments 遗留。

## 5. 证据文件（本机，`.mnemon/` 为 gitignored）

目录：`.mnemon/evidence/frontend-142-2026-10-20/`

| 文件 | 内容 |
|---|---|
| `01-initial.png` | 首屏：真实源、干净线程、已连接 |
| `02-confirmation.png` | 确认单（等您确认） |
| `03-verification.png` | 验证码步骤（等您验证） |
| `04-code-entered.png` | 验证码已填入专用框 |
| `05-result.png` | 转账成功结果卡 + 只读确认/验证记录 |
| `06-reload-readonly.png` | 同会话刷新后的只读恢复 |
| `07-new-session-readonly.png` | 新会话跨会话 F39 回放 |
| `walkthrough.json` | 逐步记录、API 调用、`checks` 与 `verdict=PASS` |
| `walkthrough.cjs` | 可复跑脚本（`node walkthrough.cjs`；需系统 Edge + `npm i --no-save puppeteer-core`） |

复跑前提：按 `backend/app/agent_platform/LOCAL-DEV.md` 启动后端（8000），在 PR 前端目录 `npm run dev`（5173，`real-api`），然后 `node walkthrough.cjs`。

## 6. 覆盖与不覆盖

- 本证据只覆盖**转账低风险主路径**（500 元：确认 + 基础验证码），对应场景 FE-01 / FE-03 / FE-04 的主路径与恢复。
- 不覆盖：501 中风险双因子（管理员模拟人脸独立会话）、502 高风险终止、600 修改流程；不覆盖账单（票 04，顺延 v0.5）、主入口替换与全面适老化回归（票 05，顺延 v0.5）。
- 本证据为 AI 代执行，不代表 Ringo 本人安全审查；确认 / 验证交互审查按 **PM 2026-10-20 豁免**留痕（详见 PR #142 收口评论）。

## 7. 合入后复核（同一提交）

main `92ee700` 独立 worktree：`npm ci` → `npm test -- --run` **4 文件 / 34 passed** → `npm run build` 通过（37 modules，337.58 kB，产物哈希与 PR head 一致）。
