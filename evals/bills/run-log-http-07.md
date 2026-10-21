# 票 07 · HTTP 报告／导出运行台账（2026-10-20）

状态：部分业务评测，非完整前后端联合验收。

当前源码以主线 `3d1ea907d6185db234ea1bf666f863820ba64bff`（后端 tree `714f633811cb1121ac039c925d35585475bb341b`）为基准，包含从历史 `test/bills/report-http-evidence-07` 迁入的 7 项端到端 HTTP 场景与运行器，旧固定后端树已更新。本源码的真实 full-checkout 实跑已完成：[GitHub Actions #39426333629](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/39426333629)，固定被测 SHA `e1111830cece552da8009ca474c9a7db3058571d`、Python 3.12.15；`run_http_evidence.py --revision e1111830cece552da8009ca474c9a7db3058571d` **7 collected / 7 passed / 0 failed / 0 skipped / 0 error**，87 次 HTTP 请求。逐字节核验 136 份 Git 源码、60 个真实应用导入模块；执行银行流水与余额不变检查。

- [原始 gzip](evidence/2026-10-20/20261020T125749371975Z-python3.12.15-http-l03-exports-e1111830cece.json.gz) 的压缩 SHA256 为 `2fe017da135cac9e4efb6fb62028913ba6bbd49417e1d54a4dea2111f6dc9244`，解压 JSON SHA256 为 `b8a8eced69287b0601409f0d7491e3314cb11f965caafd051ad7cc8100ea0025`；原始 Git 二进制 Blob `445e3b73c78316c55055524ceb76b19d0c18317c`。入库归档提交不改受测源码。
- 报告仍为 `overall_status=partial`、`full_ticket_acceptance=false`，不是所有 BF01—BF07、TLS 部署、真实模型或 React 页面都通过。

历史基线 2026-10-19：七场景共87次 HTTP请求的原始报告仅对应历史被测源码，见 [票07正式实施记录](../../.scratch/v04-ethan-bills-backend/issues/07-integration-evidence.md)。未把历史计数继承为此次真实运行。

本测试涉及既有安全门与模拟银行，但风险输入和规划器不是生产真实策略；真模型、浏览器与专业安全签核仍需各 Owner 独立证据。
