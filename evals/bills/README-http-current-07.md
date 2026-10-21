# 票07（2026-10-21）：重新锁定 main 后端树并扩充 HTTP 专项

> **状态：代码已提交，合并/专项复跑待验收；不得称 15/15 已通过。**  
> Ticket `v04-ethan-bills-backend/07` · Owner Ethan · 仅 `evals/bills/`。

## 两个源锁定常量已改

- `COMPOSITION_REVISION = 0d829d5a458d553ad0d975709b88f1f4b8a0529f`（本轮开工时最新 main）。
- `BACKEND_TREE = aa85d882c8c355242950f42c721d7cc512998068`（同一 commit 下真实 `git rev-parse <commit>:backend` 值）。
- `run_http_evidence.py` 仍在运行**前、后**比对全量已跟踪 backend 和 eval/bills 的 Git Blob SHA，以及必要公共文档，缺源码/模块导入/重复case/跳过/失败/非法资金副作用都拒绝 Passed。禁止用老分支 gzip 冒充新主线。

## 场景内容：7 + 8 = 15

- **历史第一批** BILL-HTTP-01—07：真实 L03 报告/普通卡片 F21—F24、敏感明细验证码、错误/过期、越权、会话变化；2026-10-20 老受测源码已在 [Actions #39426333629](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/39426333629) 7/7、87 HTTP 请求通过。它仅证明当时的源码。
- **本轮第二批候选** BILL-HTTP-X01—08：L01 汇总/分类明细/原任务 F10、L02 候选选择/周期扫描/空候选/专用取消、L03 报告生成后使用银行真实验证码验证并导出带 `=` 和 `@` 公式型文本的 CSV，断言单元格安全前缀。这八例尚需在本期新 head 实跑。
- 每条都用真实 `TestClient/FastAPI/ApiService/AgentHarness`、受控银行只读与已授权任务；仅规划器和LOW/公开准入事实为显式测试替身。CSV附加样本仅通过测试银行 `seed_ledger_rows` 插入，计算资金SHA基线在插入之后。

## 实跑命令

```bash
python -m pytest -q evals/bills/test_report_http_eval.py evals/bills/test_http_extra_eval.py
python evals/bills/run_http_evidence.py --revision "$(git rev-parse HEAD)"
```

**必须**全量检出仓库，先确保上述 `--revision` 对应的 `backend` Git Tree 与固定常量相等；若 Erwin 在新 PR 合并前又改变了后端，先更新两个常量并重提带自己SHA的源代码，再运行，不要跳过核对。

专项 runner 应收集恰好15例，输出 `evals/bills/evidence/2026-10-21/` 的新 JSON.gz、两类 SHA256、实际通过/失败/跳过数、真实 HTTP 请求条数与包含失败的逐例记录。它不会自动由当前 `Repository checks` workflow运行，那个CI只跑 backend + MockBank。

## 仍未覆盖（不可误报）

- SSE 正向重连/失效、导出验证码重发/取消/重复提交、更多会话过期和攻击性HTML全链路仍待另加自动化；
- Live GLM 与真实 React 页面已由 Erwin/前端线另有独立证据，不混算成同一 TestClient运行；
- 票06的各类异常补量是另一PR，不在本票目录以外夹带；
- v0.4 BF01—BF07联合验收与Ringo真人安全审查仍为各负责人决定。票07和交付包在完成这些门槛前均为`in_progress / partial`。
