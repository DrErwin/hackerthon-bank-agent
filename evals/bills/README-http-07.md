# 票 07 · 账单 L03 报告、F21—F24 真实 HTTP 验证（阶段一）

2026-10-20 更新（2026-10-21 按审查意见更正说明文字）。这一增量对**已合并**的 L03 报告模块和真实 FastAPI API 资源/导出接口执行 7 项 in-process TestClient 业务验证；Harness、SQL 持久化、B01/B08 种子银行、SecurityGate 与银行验证码服务是真实项目组件。规划器选 L03 和 LOW/授权策略采用明确声明的测试替身，不代替实际真实模型、专业安全或 React 浏览器验收。

- [场景与公共契约对应](report-http-cases.md) / [机器场景 manifest](report-http-cases.json)，BILL-HTTP-01..07
- [执行入口](run_http_evidence.py) 和 [测试源码](test_report_http_eval.py)
- [本期运行结果](run-log-http-07.md)：受测源码 SHA、gzip 和 SHA256、失败响应口径（见场景表 BILL-HTTP-05）、资金副作用对照
- 旧 2026-10-19 七场景/87 次请求的原始报告继续保留在源分支 `test/bills/report-http-evidence-07`，不能当作此次源 SHA 的新实跑。

## 受测源码与当前主线

- 受测源码：`e1111830cece552da8009ca474c9a7db3058571d`（父提交 `3d1ea907d6185db234ea1bf666f863820ba64bff`，仅可在 `origin/ci/bills-07-evidence-20261020` 取得），后端树 `714f633811cb1121ac039c925d35585475bb341b`，Python 3.12.15。
- 当前 PR 基线 `3a6d016` 的后端树为 `aa85d882c8c355242950f42c721d7cc512998068`。受测提交**不是**该基线的祖先；gzip 核验的 136 份源码中有 10 份与当前主线不同，`tested_revision`/`backend_tree` 已记录在报告内。
- 因此本归档是**历史固定源码的部分证据，不是新 main 的实跑**。新 main 专项须按 runner 声明的要求更新 `COMPOSITION_REVISION`/`BACKEND_TREE`，建立新的受测阶段后另行取证。

## 严格范围

本增量是 `phase_result=Passed` 时的**部分场景证明**；`full_ticket_acceptance=false`。尚缺其他 HTTP 故障路径、L01/L02 全链路、浏览器真实交互和真人安全复核；真实模型 L03 阶段二证据由平台票 05 另外登记。绝不把已测试 HTTP 接缝说成 TCP/TLS 部署通过。

## 复跑

```bash
# 1) 在受测提交的 LF 检出上逐字节复跑 runner（Windows 默认 CRLF 检出会被 runner 按 Git blob 拒绝）
git checkout e1111830cece552da8009ca474c9a7db3058571d
python -m pytest -q evals/bills/test_report_http_eval.py
python evals/bills/run_http_evidence.py --revision e1111830cece552da8009ca474c9a7db3058571d
```

runner 要求工作树与受测提交逐字节一致（Git blob 比对，不做换行归一化），因此请在 `core.autocrlf=false` 的检出或 Linux 环境复跑；`pytest` 用例本身不依赖固定组合，可直接在任意基线运行。

## 归档后文字更正（2026-10-21）

审查发现说明文字沿用了 2026-10-19 旧阶段的受测组合与依赖状态，已更正：受测组合 SHA/后端树、平台默认注册状态、前端交付状态、失败验证码措辞。gzip 原始报告与运行器/测试代码未改，7 场景/87 请求与断言不变。逐字节核验仍以受测提交 `e1111830…` 为准。
