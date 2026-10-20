# 票 07 · 账单 L03 报告、F21—F24 真实 HTTP 验证（阶段一）

2026-10-20 更新。这一增量对**已合并**的 L03 报告模块和真实 FastAPI API 资源/导出接口执行 7 项 in-process TestClient 业务验证；Harness、SQL 持久化、B01/B08 种子银行、SecurityGate 与银行验证码服务是真实项目组件。规划器选 L03 和 LOW/授权策略采用明确声明的测试替身，不代替实际真实模型、专业安全或 React 浏览器验收。

- [场景与公共契约对应](report-http-cases.md) / [机器场景 manifest](report-http-cases.json)，BILL-HTTP-01..07
- [执行入口](run_http_evidence.py) 和 [测试源码](test_report_http_eval.py)
- [本期运行结果](run-log-http-07.md)：固定源码 SHA、gzip 和 SHA256、不同失败响应口径、资金副作用对照
- 旧 2026-10-19 七场景/87 次请求的原始报告继续保留在源分支 `test/bills/report-http-evidence-07`，不能当作此次源 SHA 的新实跑。

## 严格范围

本增量是 `phase_result=Passed` 时的**部分场景证明**；`full_ticket_acceptance=false`。尚缺其他 HTTP 故障路径、L01/L02 全链路、浏览器真实交互和真人安全复核；真实模型 L03 阶段二证据由平台票 05 另外登记。绝不把已测试 HTTP 接缝说成 TCP/TLS 部署通过。

```bash
python -m pytest -q evals/bills/test_report_http_eval.py
python evals/bills/run_http_evidence.py --revision "$(git rev-parse HEAD)"
```
