# 票 07 · HTTP 报告／导出运行台账（2026-10-20）

状态：部分业务评测，非完整前后端联合验收。

当前源码以主线 `3d1ea907d6185db234ea1bf666f863820ba64bff`（后端 tree `714f633811cb1121ac039c925d35585475bb341b`）为基准，包含从历史 `test/bills/report-http-evidence-07` 迁入的 7 项端到端 HTTP 场景与运行器，旧固定后端树已更新。本源 SHA 的全检出实跑、原始 gzip、解压 SHA256 **尚未归档**，待新 GitHub Actions 复核后才能填写 Passed 结果。

历史基线 2026-10-19：七场景共87次 HTTP请求的原始报告仅对应历史被测源码，见 [票07正式实施记录](../../.scratch/v04-ethan-bills-backend/issues/07-integration-evidence.md)。未把历史计数继承为此次真实运行。

本测试涉及既有安全门与模拟银行，但风险输入和规划器不是生产真实策略；真模型、浏览器与专业安全签核仍需各 Owner 独立证据。
