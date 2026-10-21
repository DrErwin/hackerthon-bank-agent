# 票07 · 当前 main HTTP 专项运行台账（2026-10-21）

状态：账单项 HTTP 专项 15/15 通过；票07整体仍为 partial，不是 BF01—BF07 联合验收或安全签核。

- 受测源码：`4254949cc81f4c86a64076ec09f48e77b9801273`（本 PR 分支 rebase 到最新 main `ca3f579d22d0261ff4466e8c4a5d7317ee9f75e2` 后的证据提交）。
- 受测后端树：`aa85d882c8c355242950f42c721d7cc512998068`（`git rev-parse 4254949:backend`，与 runner 常量一致；main 自 `0d829d5` 起只新增 `evals/security/` 文件，后端树未变）。
- 执行方式：PM Erwin 授权代行；本地 Windows 全量检出，AI 执行与审查，非 Ethan 本人执行。
- 环境：Python 3.12.3、pytest 9.1.1、pydantic 2.13.5、fastapi 0.141.1、starlette 1.7.0、httpx 0.28.1、langgraph 1.2.12、deepagents 0.7.19。
- 工作树：`D:\hb-worktrees\pr210`，已设 `git config core.autocrlf false`（runner 按 Git Blob 逐字节比对，Windows 默认 CRLF 会被拒绝）。

## 命令

```powershell
cd D:\hb-worktrees\pr210
$env:PYTHONPATH="D:\hb-worktrees\pr210\backend"
D:\hackerthon-bank-agent\backend\.venv\Scripts\python.exe -m pytest -q evals/bills/test_report_http_eval.py evals/bills/test_http_extra_eval.py
D:\hackerthon-bank-agent\backend\.venv\Scripts\python.exe evals/bills/run_http_evidence.py --revision 4254949cc81f4c86a64076ec09f48e77b9801273
```

首次预跑 pytest 结果为 `15 passed in 24.62s`；正式 runner 内部再次收集并执行同一 15 例，`15 passed in 23.53s`。两次都是真实 HTTP/TestClient 执行，不是沿用旧归档。

## 逐例结果（正式 runner）

| 场景 | HTTP 请求 | 结果 |
|---|---:|---|
| BILL-HTTP-01 | 6 | passed |
| BILL-HTTP-02 | 8 | passed |
| BILL-HTTP-03 | 12 | passed |
| BILL-HTTP-04 | 16 | passed |
| BILL-HTTP-05 | 14 | passed |
| BILL-HTTP-06 | 16 | passed |
| BILL-HTTP-07 | 15 | passed |
| BILL-HTTP-X01 | 4 | passed |
| BILL-HTTP-X02 | 4 | passed |
| BILL-HTTP-X03 | 6 | passed |
| BILL-HTTP-X04 | 5 | passed |
| BILL-HTTP-X05 | 4 | passed |
| BILL-HTTP-X06 | 4 | passed |
| BILL-HTTP-X07 | 5 | passed |
| BILL-HTTP-X08 | 9 | passed |
| **合计** | **128** | **15 passed / 0 failed / 0 skipped / 0 error** |

- collected 15；`tier_counts = {in_process_http_real_l03: 7, in_process_http_real_bills_phase2: 8}`。
- 银行为真实种子库：6 个真实验证挑战记录；逐例 `funds_submit_calls=0`、`accounts_ledger_unchanged=true`，无转账/代扣提交。
- 源码核验：145 份 backend + `evals/bills` 源码/JSON/TOML 与受测提交逐字节一致；64 个 `app.*` 真实模块导入均在受测源码内；运行前后复核一致。
- 运行时间 UTC `2026-10-21T12:20:49.426783Z`–`2026-10-21T12:21:14.325967Z`（约 24.9 秒）。

## 归档

- 路径：[evidence/2026-10-21/20261021T122114556792Z-python3.12.3-http-l03-exports-4254949cc81f.json.gz](evidence/2026-10-21/20261021T122114556792Z-python3.12.3-http-l03-exports-4254949cc81f.json.gz)
- gzip SHA256：`e4666b67a6d5e5c15ae4eac87cd8cb24b2b1365a9afdd1822fd0f905866f42a4`
- 解压 JSON SHA256：`954fba89522b981af6636ef88501f88c1bd90018ea8e2f5ff1fd97cf92b6f282`
- Git 二进制 Blob：`b7fc4b33018d19d72249d313ff20c55de6da8de0`
- 文件大小：35,790 字节；命名沿用 #208 约定 `*-http-l03-exports-<sha12>.json.gz`。
- 报告字段：`phase_result=Passed`、`exit_code=0`、`overall_status=partial`、`full_ticket_acceptance=false`、`runtime_sources_verified=true`、`evidence_errors=[]`。

## 敏感数据核验

- 未落盘：HTTP 请求体原文、验证码原文（含 `/demo-code` 响应体）、Cookie 签名、CSV/下载响应全文、原始银行流水行。
- 实际保留：请求方法/路径/状态码/响应 SHA256 与字节数、验证结果枚举（verified/rejected）、会话 UUID（36 位，无 `.` 签名段）、任务/报告/导出/挑战标识、银行只读调用元数据（账户、时间范围、行数、结果）。
- 解压后的 JSON 中检索不到测试插入的 `EVAL-CSV-FORMULA-ONLY`、`EVAL-FORMULA-TEST`、`HYPERLINK`、`@SUM(1,1)` 等样本内容；六位数字仅为时间戳微秒、响应字节数和金额，无验证码值。

## 复跑前置

1. 全量检出且工作树干净，`git rev-parse HEAD:backend == aa85d88…`。
2. Windows 必须 `git config core.autocrlf false`，否则逐字节校验失败。
3. 若 main 后端树再次变化，先更新 `COMPOSITION_REVISION` / `BACKEND_TREE` 并提交新的受测 head，再运行；不得跳过源码核验或用旧 gzip 冒充。

## 边界

本台账只证明 15 个 TestClient/真实 HTTP 路由 + 真实后端模块 + 真实种子银行场景。未覆盖 SSE 正向重连/失效、验证码重发/取消/重复提交、攻击性 HTML 全链路、Live GLM、真实 React 页面和 Ringo 真人安全审查；票07与 v0.4 联合验收在这些门槛完成前仍为 `in_progress / partial`。
