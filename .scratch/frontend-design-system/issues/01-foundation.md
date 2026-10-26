# frontend-design-system/01：统一设计系统并接入常用组件

Type: 开发
Owner: Erwin
Directory: `frontend/`
Status: in_progress
Accepted by: 本对话 AI（用户明确授权设计系统与组件接入）
Accepted at: 2026-10-26
Spec: [规格](../spec.md)

## What to build

按[设计系统](../../../frontend/DESIGN.md)和[完整交互方案](../../../frontend/交互改造方案-v0.2.md)交付依赖、变量、组件展示页，以及常驻服务、详情抽屉、等待和字号反馈的首批接入。

## Acceptance criteria

- [ ] 共用库进入 lockfile，旧页面与现有业务契约仍可构建。
- [ ] 常驻服务可用，手机抽屉/桌面侧栏、等待、轻提示和字号可操作。
- [ ] 键盘焦点、窄屏和前端回归有证据。
- [ ] 完整设计方案、原型能力边界、下一批迁移清楚。

## Verification

实施后追加本地测试、构建、实际浏览器和独立审查结果；不代替真实后端/模型和本人体验接受。
