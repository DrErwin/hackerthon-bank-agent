# 02：通用前端底盘与契约接缝

Ticket ID: liangshuang-frontend-complete/02
Type: 开发
Owner: 梁爽
Directory: frontend/
Status: in_review
Package: [frontend-complete/packages/01：v0.4 完整前端实现与替换](../../frontend-complete/packages/01-v04-complete-frontend.md)
Spec: [梁爽完整前端实施规格](../spec.md)
Core scenarios: [FE-03、FE-04、FE-06](../../frontend-complete/spec.md)
Blocked by: [liangshuang-frontend-complete/01](01-complete-transfer-prototype.md) 经 Erwin 走查通过
Verification: 组件测试覆盖会话历史、等待、确认 / 验证只读保留、恢复入口和重复点击；构建通过；390×844 与桌面视口走查。

## 交付与验收

- 实现业务线无关的对话、等待、确认、验证码 / 模拟人脸、结果 / 报告、恢复与待核实查询组件。
- 建立基于公共契约类型的前端接缝和可明确识别的 stub，不复制契约定义。
- 业务线以插槽方式接入，不在底盘写死转账或账单事实。
- 页面保留 stub、契约 demo 与真实 API 来源标签；本票仅验收 stub，契约 demo / 真实 API 的接入与验证留票 03 / 05。

## Comments

- 2026-10-12：梁爽完成 `/v04` 通用底盘（stub 数据源 + 转账演示插槽），22 项前端测试、类型检查、生产构建通过，390×844 与 1280×800 浏览器走查通过；契约缺口 6 项列在 PR 中。提交 [PR #108](https://github.com/DrErwin/hackerthon-bank-agent/pull/108)，已请求 Erwin 走查；确认前不标记 resolved。
- 2026-10-13：按 [Erwin 返修清单](https://github.com/DrErwin/hackerthon-bank-agent/pull/108#issuecomment-6126114071) 同步最新 main，补 409 冲突后读取最新任务及 expired / superseded 确认单只读测试。本票结论限于 stub；契约 demo / 真实 API 留票 03 / 05。
- 2026-10-13 返修验证：24 项前端测试、生产构建、文档链接及差异空白检查通过；本轮 Standards / Spec 双轴复审均无发现。真实接口未验收。
- `AdminDemoPage`（F27/F28）是模拟人脸跨端闭环的支撑；`GalleryPage` 是 FE-06 组件状态与适老化走查入口，因此保留在本票。
- Ringo 审查本票由 Erwin 于 2026-10-12 按 PM 决定豁免，非 Ringo 本人审查；票 03 / 05 的真实接口接入仍需安全审查。Erwin 委托 AI 的手机 / 桌面及键盘回车走查已通过，见 [走查结果](https://github.com/DrErwin/hackerthon-bank-agent/pull/108#issuecomment-6126223764)；本票保持 in_review，待返修复验和合并。
