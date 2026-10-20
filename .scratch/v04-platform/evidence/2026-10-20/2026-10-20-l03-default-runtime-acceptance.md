# 票 05 阶段二 L03 正式验收证据（默认运行时，2026-10-20）

- 票：[v04-platform/05：真实账单模块接入平台与纵向联调](https://github.com/DrErwin/hackerthon-bank-agent/blob/main/.scratch/v04-platform/issues/05-real-bills-integration.md)（阶段二 L03 部分）
- 总跟踪：[Issue #123](https://github.com/DrErwin/hackerthon-bank-agent/issues/123)（保持 OPEN）
- 执行：AI 实施会话（Lead）代执行 · **AI 代执行留痕，非真人审查**；PM 2026-10-20 13:47 口径「5A 授权 AI 代做、Erwin 审后合」
- 基线：`origin/main` = `d133f376675ede2551f03a7378c83ac53bdd2801`（下文简称 `d133f37`）
- 工作树：`D:\hb-worktrees\platform-stage2`（分支 `test/platform/l03-acceptance-20261020`，只新增本票测试与证据，**未改生产代码**）
- 范围切分：本单**只验收 L03**。L02 真实链路（安全白名单 [#187](https://github.com/DrErwin/hackerthon-bank-agent/issues/187) + 平台注册 [#190](https://github.com/DrErwin/hackerthon-bank-agent/pull/190)）由其它会话负责，不在本单；前端账单插槽联调归前端票 04。

## 1. 环境

| 项 | 值 |
|---|---|
| 运行时 | 默认部署组合 `app.agent_platform.local_demo:build_runtime`（`create_app` 装配真实 API） |
| 组件 | 真实 bills 模块（L01 `bills.summarize` + L03 `bills.generate_report`，真实 `REPORT_MANIFEST`）、真实本地安全策略 `DemoSecurityPolicy`（`policy_version=v04-local-demo-read-2`）、真实模拟银行（`seed_flow_history` 播种） |
| 模型（A 层） | 智谱 `glm-5.3`，**Coding Plan 入口** `https://open.bigmodel.cn/api/coding/paas/v4/`；planner `config_version=zhipu-local-ee7f3f0a838aa9a5`；配置来自本机 gitignored `.env.local-demo.json`（未入库、未回显） |
| 模型（B 层） | 仅模型回复用脚本替身（与 `test_local_demo.py` 同一模式），其余全部真实 |
| 传输 | FastAPI TestClient（进程内 ASGI）；**不是**部署的 TCP/TLS 服务，也没有浏览器 |
| Python / pytest | 3.12.3 / 9.1.1（Windows 11） |
| 数据目录 | 每次运行全新临时目录；银行按银行时钟重新播种（A1=120 条、A5=23 条种子流水），不触碰开发者演示库 |

## 2. 证据分层（不要混写）

- **A 层：真实模型 + 默认运行时**——本节第 3 段，2 次独立运行，`real-model-run*.json`。这是本票的「真实模型」证据。
- **B 层：同一默认运行时的可执行验收用例**——`backend/app/api/test_local_demo_l03_acceptance.py`，只把模型回复换成脚本替身，进 CI 且可重复；它证明链路可回归，**不**当真实模型证据。
- 两层都不是前端页面验收，也不是 Ringo 真人安全签核。

## 3. A 层：真实 GLM 两次独立运行（全部检查通过）

| 运行 | 时间（Asia/Taipei） | 时长 | 任务 ID | 报告 ID |
|---|---|---|---|---|
| 第 1 次 | 14:36:15–14:36:29 | 14.52s | `36395aee-7ddd-410f-aeed-12c6da2c8e49` | `fb8a7646-714b-4375-bc91-96a1034d4d68` |
| 第 2 次 | 14:36:33–14:36:49 | 16.05s | `c88ff600-347c-4bce-be50-aa2a46e08268` | `0392e2ce-6935-41ae-a415-e6f843e23c0f` |

链路与结果（两次一致）：

1. **自然语言路由**：消息「帮我生成一份上个月的账单报告」→ 真实 GLM 规划入口提出 `bills.generate_report`（`routing_attempts` 第 1 条即命中，无需换说法）→ 平台建任务 `module=bills`、`status=waiting_input`，助手回复「请选择要查询的本人账户，不会替你默认选择。」
2. **等待 → 恢复**：F10 选项「所有本人账户」（另两个选项：主账户 · 尾号 0001、储蓄账户 · 尾号 0005）→ 任务 `succeeded`，task_revision=3。
3. **报告落库 + F21**：平台自动落库 `BillReport`；F21 返回内容与任务 `data` **逐字段相同**（`f21.matches_task_data=true`）。
   - scope：A1+A5，`2026-09-01T00:00:00+08:00`–`2026-10-01T00:00:00+08:00`（= 上个月，北京日历边界）
   - summary：`transaction_count=18`、`consumption_gross_fen=586400`、`consumption_refund_fen=4500`、`consumption_net_fen=581900`、`transfer_in_fen=821000`、`transfer_out_fen=0`
   - `monthly_average_fen=586400`、`statistical_days=30`、`average_basis` 含「按统计天数折算，每月30天；不预测未来实际支出」
   - 卡片只含契约字段（`report_id/scope/summary/spoken_summary/monthly_average_fen/statistical_days/average_basis/generated_at`），**不含** `transactions` 等原始全量明细
   - 与银行对账：同 scope 内真实 B08 流水 A1=14 条、A5=4 条，合计 18 = `transaction_count`
4. **事件**：`report_ready` 恰好 1 次，payload `{task_id, report_id}`、`module=bills`；末条 `task_updated` 的 `module=bills` 且 `payload.data.report_id` 为同一报告（Issue #122 第 1 项）。
5. **卡片导出（F22/F23/F24）**：kind=card 即时 `ready`、`task_id=null`、`text/html`；下载 200、`Cache-Control: no-store`、1320 字节，**不含**任何逐笔 `transaction_id`。
6. **明细导出（F22—F24）**：kind=details → `waiting_verification`，导出任务 `module=bills`、`waiting_approval`、交互 `kind=verification`；验证前 F24 = **409**；F19 演示码 200 且 `no-store`；F17 验证码 → `verified`、任务 `succeeded`；F23 → `ready`；F24 CSV 200、`text/csv`、`no-store`，**18 行**、冻结表头：
   `occurred_at,account_id,direction,nature,category,amount_fen,counterparty_name,counterparty_account_masked,channel,summary,transaction_id`
7. **两次运行确定性**：全部业务数字相同；CSV SHA256 两次均为 `7551f48dee1d7b80dc7cdd4bda633f7327e3155fb4ff0a1dd373017f8b2651ec`；卡片 SHA 不同属预期（含 report_id/generated_at）。
   - 第 1 次卡片导出 `c795acff-264a-4d64-a9f8-558519797275`，明细导出 `ced142b1-9646-4ad8-b5fc-cd6b2f026696`，导出任务 `2ea7d490-f779-4772-ac94-5c0029f4041d`
   - 第 2 次卡片导出 `168778c4-e4ce-42fb-8c64-126fe9daf8af`，明细导出 `44291cc3-9b97-4bcf-adea-b4b16166da60`，导出任务 `97e5350d-da89-4b82-9a9b-e0c940c8f477`
8. **安全边界**：
   - 另一已登录身份（`demo-admin`，`role=admin`）请求本人报告/导出/下载：F21、F23（card/details）、F24（card/details）全部 **404**；随机报告 ID 也 404
   - 审计（管理端 HTTP）：25 条事件，含 `tool.started/tool.finished` 各 5、`security.decided` 10、`task.transition` 2、`model.started/finished`、`recovery.checked`；`tool.started` 与 `tool.finished` 的 `tool_call_id` **5/5 成对**，`security.decided` 全 `allow`
   - 零资金动作：A1/A5 余额两次运行前后不变，非种子流水 A1/A5 均为 0
9. **分享意图不增权**：消息「…分享给孩子看」→ 报告正常生成（`share_request` 意图）；明细导出仍为 `waiting_verification`（未预先授权、未 ready）。系统没有第三方身份或外发通道，本单也未新增。
10. **脚本自检**：`checks` 26 项全部 `true`，`verdict=completed`（见 JSON 的 `checks`）。

## 4. B 层：可执行验收用例（CI 回归）

文件：`backend/app/api/test_local_demo_l03_acceptance.py`（新增，2 个用例；仅测试代码，无生产改动）

| 用例 | 覆盖 |
|---|---|
| `test_l03_report_chain_f21_f22_f24_and_122_seams` | 默认装配（L03 来自真实 `REPORT_MANIFEST`）→ 消息 → 等待账户 → F10 恢复 → `BillReport` 落库/F21/`report_ready`/`task_updated` 真载荷 → 卡片导出 → 明细等待验证 → F24 409 → F17 验证 → CSV 冻结表头与银行流水逐行对账 → 零资金 |
| `test_l03_cross_identity_denials_share_intent_and_audit` | 管理身份跨用户 404（F21/F23/F24、随机 ID）、审计配对与 `security.decided` 全 allow、`share_request` 不增权、零资金 |

命令与输出（2026-10-20 14:38 实测）：

```powershell
# backend/ 下
backend/.venv/Scripts/python.exe -m pytest app/api/test_local_demo_l03_acceptance.py -q
# 2 passed in 5.61s

backend/.venv/Scripts/python.exe -m pytest app/api -q
# 100 passed in 157.72s

backend/.venv/Scripts/python.exe -m pytest -q
# 967 passed in 303.78s（= 分支树全量，含本票新增 2 项）

backend/.venv/Scripts/python.exe -m pytest -q ../evals/mockbank/test_mockbank_eval.py
# 14 passed in 1.04s
```

## 5. Issue #122 三处接缝在真数据下的复验

| # | 接缝 | 真数据复验结果 |
|---|---|---|
| 1 | 第二模块 `task_updated` 带真实载荷 | 末条 `task_updated` `module=bills`，`data` 含完整 `BillReport`（scope/summary/report_id）——A 层两次 + B 层断言 |
| 2 | harness 恢复解析可推进 | 账单任务 `waiting_input` → F10 选项 → `succeeded`；载荷是账单报告（无 `operation_id`），未被按转账定型解析失败——A 层两次 + B 层断言 |
| 3 | 导出任务 `module=bills` | 明细导出任务视图 `module=bills`，其 `task_updated` 事件 `module` 亦为 `bills`；导出任务不进 harness 能力解析，沿自身平台任务等待/完成——A 层两次 + B 层断言 |

## 6. 契约字段核对

- **F21 `BillReport`**（契约 §5.3）：`report_id/scope/summary/spoken_summary/monthly_average_fen/statistical_days/average_basis/generated_at` 八字段齐全；`summary` 含 `scope/as_of/source_as_of/transaction_count/consumption_*/transfer_*/categories/comparison`；无原始逐笔明细。
- **F22—F24 `ExportView`**（契约 §6.7）：`export_id/kind/status/task_id/file_name/media_type/download_path/error`；card → `task_id=null`、即时 ready；details → `task_id` 必填、`waiting_verification`；`download_path` 为应用内相对路径（`/api/v1/exports/{id}/download`），下载响应文件流 + `no-store`。
- **§6.6 事件**：`task_updated` payload 为 `TaskView`（含 `module`、`data`）；`report_ready` payload 仅 `{task_id, report_id}`。
- **契约 §5.3 L03 边界**：`purpose=share_request` 只是意图，不授予第三方权限、不发送给子女；明细导出未被 L03 绕行，仍走 §6.7 重新验证。

## 7. 未覆盖 / 本单不声称

- **L02 真实链路**（`bills.detect_anomalies`）不在本单：安全白名单 [#187](https://github.com/DrErwin/hackerthon-bank-agent/issues/187) 与平台注册 [#190](https://github.com/DrErwin/hackerthon-bank-agent/pull/190) 归其它会话；当前默认 `public_catalog()` 只有 L01+L03（另含转账/订阅），L02 仍不在目录。
- **前端账单插槽与纵向联调**（票 05 交付 3、BF01—BF07）未做：归前端票 04（梁爽）与 [v04-bills/02](../../../v04-bills/packages/02-v04-acceptance.md) 联合验收。
- **部署形态**：A 层为进程内 ASGI TestClient，不是 uvicorn TCP/TLS、反向代理或浏览器；`no-store`/Cookie/Origin 的部署侧行为未在本证据覆盖。
- **安全真人签核**：Ringo 本人对安全白名单（#177/#187）的签核仍缺；本单是功能验收，**不是**安全专业结论。
- **账单数字正确性**：分类/月均等统计口径归账单线 BF03/BF06；本单只核对字段、计数与「报告 scope 内银行流水条数一致」。
- 本单**不关闭** Issue #123，也不改版本收口材料。

## 8. 原始证据文件

目录：`.scratch/v04-platform/evidence/2026-10-20/`

| 文件 | 内容 |
|---|---|
| `run_real_model_l03.py` | 可复跑的 A 层 runner（真实 GLM + 默认运行时；不含密钥） |
| `real-model-run.json` | 第 1 次运行原始记录：路由/任务/报告/事件/导出/审计/银行/`checks` |
| `real-model-run-repeat.json` | 第 2 次独立运行原始记录（对照确定性） |
| `pytest-l03-acceptance.txt` | B 层用例命令与输出原件 |
| `2026-10-20-l03-default-runtime-acceptance.md` | 本文件 |

原始记录不含密钥、验证码明文、Cookie 或 CSV 全文；`config_source` 只记配置文件路径。

## 9. 复跑

```powershell
# B 层（无需模型密钥）
cd <repo>\backend
.venv\Scripts\python.exe -m pytest app/api/test_local_demo_l03_acceptance.py -q

# A 层（需本机 .env.local-demo.json，不得提交）
cd <repo>
backend\.venv\Scripts\python.exe .scratch\v04-platform\evidence\2026-10-20\run_real_model_l03.py `
    <repo>\.env.local-demo.json .scratch\v04-platform\evidence\2026-10-20\real-model-run.json
```
