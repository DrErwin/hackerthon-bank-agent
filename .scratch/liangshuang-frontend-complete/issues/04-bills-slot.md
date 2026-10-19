# 04：账单业务插槽

Ticket ID: liangshuang-frontend-complete/04
Type: 开发
Owner: 梁爽
Directory: frontend/
Status: planned（v0.4，**PM 2026-10-20 01:45 决定：不顺延，本期完成**〔撤回同日 01:41 的 deferred 记录〕。两个硬前置在平台/安全目录：① 平台 `local_demo.py`/`build_runtime` 只 `register_bills`（L01），`bills.generate_report`（L03）未注册；② 安全 `demo_policy.py` 的 `_capabilities` 只收 `BILLS_MANIFEST`（L01），未收 `REPORT_MANIFEST`。前置解除前只能做明确标注的 stub，不得记真实联调）
Package: [frontend-complete/packages/01：v0.4 完整前端实现与替换](../../frontend-complete/packages/01-v04-complete-frontend.md)
Spec: [梁爽完整前端实施规格](../spec.md)
Core scenarios: [FE-02、FE-03、FE-06](../../frontend-complete/spec.md)
Blocked by: [liangshuang-frontend-complete/02](02-frontend-shell.md)；真实联调依赖 `v04-bills/01` 发出可调用公开能力信号
Verification: 用契约形状 stub 走通入口、明细与报告；公开能力可调用后核对真实响应、失败与恢复，不把 stub 通过记为真实联调。

## 交付与验收

- 在同一底盘接入账单三类能力入口、明细和报告卡片。
- 报告金额、分类、异常线索与状态只展示账单公开能力返回。
- 公共接口未就绪时只使用明确标注的契约形状 stub，不发出可联调完成信号。
- 缺少必要数据格式时提出契约变更，不在前端自定义平行 schema。

## Comments
- 2026-10-20（PM 01:45 撤回顺延，AI 代填）：本票**留在 v0.4 完成**。同日 01:41 记录的「顺延 v0.5 / v0.4 不做 stub 切片」作废。前置不变：`bills.generate_report`（L03）需平台注册 + 安全白名单收录 `REPORT_MANIFEST`；在前置解除前只做明确标注的 stub，不发出可联调完成信号。
