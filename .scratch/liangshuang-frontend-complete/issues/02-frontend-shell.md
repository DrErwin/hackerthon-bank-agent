# 02：通用前端底盘与契约接缝

Ticket ID: liangshuang-frontend-complete/02
Type: 开发
Owner: 梁爽
Directory: frontend/
Status: planned
Package: [frontend-complete/packages/01：v0.4 完整前端实现与替换](../../frontend-complete/packages/01-v04-complete-frontend.md)
Spec: [梁爽完整前端实施规格](../spec.md)
Core scenarios: [FE-03、FE-04、FE-06](../../frontend-complete/spec.md)
Blocked by: [liangshuang-frontend-complete/01](01-complete-transfer-prototype.md) 经 Erwin 走查通过
Verification: 组件测试覆盖会话历史、等待、确认 / 验证只读保留、恢复入口和重复点击；构建通过；390×844 与桌面视口走查。

## 交付与验收

- 实现业务线无关的对话、等待、确认、验证码 / 模拟人脸、结果 / 报告、恢复与待核实查询组件。
- 建立基于公共契约类型的前端接缝和可明确识别的 stub，不复制契约定义。
- 业务线以插槽方式接入，不在底盘写死转账或账单事实。
- 测试和页面能区分局部 stub、契约 demo 与真实 API 状态。

## Comments
