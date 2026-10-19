# 2026-10-20 前置空白/制表符补充复验

对应 [v04-ringo-security/04：明细导出通知口径回归](../../../../.scratch/v04-ringo-security/issues/04-details-export-regression.md) 与 [Issue #161](https://github.com/DrErwin/hackerthon-bank-agent/issues/161) 的「前置空白」要求。AI 按 Ringo 授权执行，真人专业批准另记。

执行入口与 2026-10-19 批次相同：`python evals/security/export_regression.py --output <仓库外新路径>`。公式型文本参数由 4 组扩为 6 组（新增 `" =1+1"`、`"\t+1"`），并断言下载值为单引号前缀后逐字保留的原文；runner 合计 20 项（10 项既有平台测试 + 10 项新增检查实例）。

2026-10-20 实跑：**20 Passed / 0 Failed**，真实模型调用 0 次。报告：

| 报告 | 解压后 sha256 |
|---|---|
| [supplement](2026-10-20-offline-export-boundary-supplement.json.gz) | 7432C090946D2408C3109BDB7639B1AA8E412CC3281AE77D468BE0836A7A4AC0 |

来源基线为报告产生时的 main `25b0738`；其后合并 #149 只改 `backend/app/security`，不影响本专项记录的文件哈希。`backend/app/api` 与 #161 修复版本自 `e43765a` 起未变。报告内记录的来源 sha256：

| 文件 | sha256 |
|---|---|
| export_regression.py | 1da62d3268a1d6375d9e78824c8b308151a6b800aa00ec5ad526f8dccf4266a1 |
| test_export_boundary.py | 6023e754fca7418f0c4787184f01ae7dcad3102ccfcaa456edd832a92a410419 |
| test_app.py | 185633853f7d56824cd522ed0d676c19fe0c97db434b43575eea55d0f57aa805 |
| test_export_secrets.py | c231106c277be1243052f5f460628b404cb3d87d239b5b2948f09418398f227b |
| service.py | bd624536358280c891c0a8707a7ebb46c66a975c3853e24ac57a89e2b0a550e0 |

边界：授权与风险为平台固定替身，报告卡片为受控 L03 契约夹具；不证明真实账单 L01—L03、生产检测器或页面验收通过。原 18 项 retest 报告（`036109E268DB504EA01C85EDEA11F19C452D3436832F0B7E4C1FCC5759D32BD0`）保持历史，不覆盖、不重写。
