# 01：补齐转账原型五类关键交互

Ticket ID: liangshuang-frontend-complete/01
Type: 设计
Owner: 梁爽
Directory: frontend/
Status: in_progress
Package: [frontend-complete/packages/01：v0.4 完整前端实现与替换](../../frontend-complete/packages/01-v04-complete-frontend.md)
Spec: [梁爽完整前端实施规格](../spec.md)
Core scenarios: P-01；为 [FE-01、FE-03、FE-06](../../frontend-complete/spec.md) 固定交互
Blocked by: None
Verification: 在 390×844 浏览器视口逐条走通候选、修改、等待、模拟人脸、刷新恢复；无横向溢出；刷新不自动重提交易；保存走查证据并交 Erwin 确认。

## 交付与验收

- 在现有 `转账-交互原型-v0.1.html` 补齐五类画面，不另建重复原型。
- 收款人候选必须由用户主动选择；修改路径可改收款人、账户或金额并回到确认。
- 验证卡支持验证码和明确标注的模拟人脸入口；不启用摄像头或采集生物信息。
- 等待态提供清楚进度且防止重复点击；结果卡保留之前的确认 / 验证记录。
- 页面刷新后只展示恢复原任务入口，由用户主动恢复，不自动提交。
- 手机视口可点击、文案清楚、无横向滚动；原型通过不宣称真实 API 联调完成。

## Comments

- 2026-10-12：梁爽确认拆票并启动本票。
