# 04：账单业务插槽

Ticket ID: liangshuang-frontend-complete/04
Type: 开发
Owner: 梁爽
Directory: frontend/
Status: planned
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
