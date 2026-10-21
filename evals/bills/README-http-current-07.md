# 票07（2026-10-21）：重新锁定 main 后端树并扩充 HTTP 专项

> **状态：已在最新 main `ca3f579` 之上实跑，15/15 HTTP 场景通过、128 次真实 HTTP 请求、零资金提交；票07整体仍为 partial。**
> Ticket `v04-ethan-bills-backend/07` · Owner Ethan · 仅 `evals/bills/`。

## 两个源锁定常量

- `COMPOSITION_REVISION = ca3f579d22d0261ff4466e8c4a5d7317ee9f75e2`（本轮开工时最新 main；其后 #211/#212/#213 只改 `evals/security/`，`backend` 树未变）。
- `BACKEND_TREE = aa85d882c8c355242950f42c721d7cc512998068`（`git rev-parse ca3f579:backend` 的真实值）。
- `run_http_evidence.py` 仍在运行**前、后**比对全量已跟踪 backend 和 `evals/bills` 的 Git Blob SHA，以及必要公共文档；缺源码/模块导入/重复 case/跳过/失败/非法资金副作用都拒绝 Passed。禁止用老分支 gzip 冒充新主线。

## 场景内容：7 + 8 = 15

- **第一批** BILL-HTTP-01—07：真实 L03 报告/普通卡片 F21—F24、敏感明细验证码、错误/过期、越权、会话变化。本轮在当前 head 重跑，仍为 7/7、87 次 HTTP 请求。
- **第二批** BILL-HTTP-X01—08：L01 汇总/分类明细/原任务 F10、L02 候选选择/周期扫描/空候选/专用取消、L03 报告生成后使用银行真实验证码验证并导出带 `=` 和 `@` 公式型文本的 CSV，断言单元格安全前缀。本轮 8/8、41 次 HTTP 请求。
- 每条都用真实 `TestClient/FastAPI/ApiService/AgentHarness`、受控银行只读与已授权任务；仅规划器和 LOW/公开准入事实为显式测试替身。CSV 附加样本仅通过测试银行 `seed_ledger_rows` 插入，计算资金 SHA 基线在插入之后。

## 正式实跑（2026-10-21）

```powershell
$env:PYTHONPATH="<worktree>\backend"
python -m pytest -q evals/bills/test_report_http_eval.py evals/bills/test_http_extra_eval.py
python evals/bills/run_http_evidence.py --revision 4254949cc81f4c86a64076ec09f48e77b9801273
```

- 受测源码：`4254949cc81f4c86a64076ec09f48e77b9801273`（rebase 到 `ca3f579` 后的证据提交；`backend` 树 `aa85d88`），运行前后 145 份源码逐字节一致、64 个真实应用模块导入全部落在受测源码内。
- 结果：15 collected / 15 passed / 0 failed / 0 skipped / 0 error，`phase_result=Passed`，`exit_code=0`；128 次 HTTP 请求（老 7 例 87 + 新 8 例 41）。
- 银行副作用：6 个真实验证挑战记录，`funds_submit_calls=0`，逐例账户/流水摘要前后一致。
- 运行时间 UTC `2026-10-21T12:20:49Z`–`12:21:14Z`（约 24.9 秒），Python 3.12.3 / Windows。
- 证据：[evidence/2026-10-21/20261021T122114556792Z-python3.12.3-http-l03-exports-4254949cc81f.json.gz](evidence/2026-10-21/20261021T122114556792Z-python3.12.3-http-l03-exports-4254949cc81f.json.gz)
  - gzip SHA256 `e4666b67a6d5e5c15ae4eac87cd8cb24b2b1365a9afdd1822fd0f905866f42a4`
  - 解压 JSON SHA256 `954fba89522b981af6636ef88501f88c1bd90018ea8e2f5ff1fd97cf92b6f282`
  - Git 二进制 Blob `b7fc4b33018d19d72249d313ff20c55de6da8de0`
- 请求体原文、验证码原文、Cookie 签名和 CSV/下载全文均未落盘：报告只保留方法/路径/状态/响应 SHA256 与计数、验证结果枚举、会话 UUID（不含签名）和逐例银行只读元数据；测试插入的公式样本标记在解压 JSON 中不存在。

## 仍未覆盖（不可误报）

- SSE 正向重连/失效、导出验证码重发/取消/重复提交、更多会话过期和攻击性 HTML 全链路仍待另加自动化；
- Live GLM 与真实 React 页面已由 Erwin/前端线另有独立证据，不混算成同一 TestClient 运行；
- 票06的各类异常补量是另一 PR，不在本票目录以外夹带；
- v0.4 BF01—BF07 联合验收与 Ringo 真人安全审查仍为各负责人决定。票07和交付包在完成这些门槛前均为 `in_progress / partial`。

详细台账见 [run-log-http-current-07.md](run-log-http-current-07.md)。
