# frontend-design-system/01：统一设计系统并接入常用组件

Type: 开发
Owner: Erwin
Directory: `frontend/`
Status: ready_for_review — 本地实现、测试、浏览器走查和两轴问题复核完成，等待体验接受与合入。
Accepted by: 本对话 AI（用户明确授权设计系统与组件接入）
Accepted at: 2026-10-26
Spec: [规格](../spec.md)

## What to build

按[设计系统](../../../frontend/DESIGN.md)和[完整交互方案](../../../frontend/交互改造方案-v0.2.md)交付依赖、变量、组件展示页，以及常驻服务、详情抽屉、等待和字号反馈的首批接入。

## Acceptance criteria

- [x] 共用库进入 lockfile，旧页面与现有业务契约仍可构建。
- [x] 常驻服务可用，手机抽屉/桌面侧栏、等待、轻提示和字号可操作。
- [x] 键盘焦点、窄屏和前端回归有证据。
- [x] 完整设计方案、原型能力边界、下一批迁移清楚。

## Verification

详见[验证与独立审查](../verification.md)。全套 108 项前端测试通过；审查修正后相关 12 项通过，构建通过。人工体验接受与真实后端/模型验收分别记录。

完整体验原型单独保存在 [codex/frontend-ux-prototype-20261026](https://github.com/DrErwin/hackerthon-bank-agent/tree/codex/frontend-ux-prototype-20261026/.scratch/frontend-ux-prototype-20261026)，便于评审首页、转账、账单、自动扣费和生活安排。原型分支用于设计验证。
