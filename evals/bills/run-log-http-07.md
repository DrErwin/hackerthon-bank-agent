# 票 07 · HTTP 报告／导出运行台账（2026-10-20）

状态：部分业务评测，非完整前后端联合验收。

受测源码提交 `e1111830cece552da8009ca474c9a7db3058571d`（父提交为当时主线 `3d1ea907d6185db234ea1bf666f863820ba64bff`，后端 tree `714f633811cb1121ac039c925d35585475bb341b`；该提交仅可在 `origin/ci/bills-07-evidence-20261020` 取得，**不在本 PR 基线 `3a6d016` 的祖先链上**）。本归档是**历史固定源码证据，不是新 main 实跑**：136 份核验源码中有 10 份与当前主线不同，新 main 专项须另建受测阶段。

实跑：[GitHub Actions #39426333629](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/39426333629)（工作流在受测提交的 CI 包装提交 `ed29ccfe` 上执行），Python 3.12.15；`run_http_evidence.py --revision e1111830cece552da8009ca474c9a7db3058571d` **7 collected / 7 passed / 0 failed / 0 skipped / 0 error**，87 次 HTTP 请求，运行时间 UTC `2026-10-20T12:57:42Z`–`12:57:49Z`。逐字节核验 136 份 Git 源码、60 个真实应用导入模块；执行银行流水与余额不变检查。

- [原始 gzip](evidence/2026-10-20/20261020T125749371975Z-python3.12.15-http-l03-exports-e1111830cece.json.gz) 的压缩 SHA256 为 `2fe017da135cac9e4efb6fb62028913ba6bbd49417e1d54a4dea2111f6dc9244`，解压 JSON SHA256 为 `b8a8eced69287b0601409f0d7491e3314cb11f965caafd051ad7cc8100ea0025`；原始 Git 二进制 Blob `445e3b73c78316c55055524ceb76b19d0c18317c`。gzip 与运行器/测试代码未改；说明文字已按归档后审查更正（见文末）。
- 136 份较 2026-10-19 阶段（125 份）新增 11 份：风险输入、平台验收、订阅 API、账单策略测试、fixture_map、arithmetic-cases、run_evidence、evidence_integrity、statistics_eval 等；另 3 份具名文档计入。
- 报告仍为 `overall_status=partial`、`full_ticket_acceptance=false`，不是所有 BF01—BF07、TLS 部署、真实模型或 React 页面都通过。

历史基线 2026-10-19：七场景共87次 HTTP请求的原始报告仅对应历史被测源码，见 [票07正式实施记录](../../.scratch/v04-ethan-bills-backend/issues/07-integration-evidence.md)。未把历史计数继承为此次真实运行。

本测试涉及既有安全门与模拟银行，但风险输入和规划器不是生产真实策略；真模型、浏览器与专业安全签核仍需各 Owner 独立证据。

## 归档后文字更正（2026-10-21）

审查发现说明文字沿用了 2026-10-19 旧阶段的受测组合（99e96737/b5f9f3aa）与「默认工厂只登记 L01」等旧表述，已按受测提交事实更正；同时补充「历史源码、非新 main 实跑」与新 main 复跑前置说明。gzip 与运行器/测试代码未改，7 场景/87 请求与断言不变。逐字节复跑请 checkout `e1111830…` 的 LF 工作树（Windows 默认 CRLF 会被拒绝）。
