# v05-demo-reset-contracts/01：补齐冻结的管理重置模型

Ticket ID: v05-demo-reset-contracts/01
Package: v05-cross-linkage/packages/01-platform-bank；B26完整重置
Spec: [规格](../spec.md)
Type: 开发
Owner: Erwin
Directory: `backend/app/contracts/`
Status: in_progress
Accepted by: 本对话AI，依据用户本轮非资料任务执行授权
Accepted at: 2026-10-27
Blocked by: None
Core scenarios: F30预览只带当前轮次；F31带后端二次确认；F32返回管理状态及实际轮次

只新增ResetPreviewRequest、ResetRequest、ResetPreview和ManagementOperation，字段与冻结契约一致；不复制API私有模型、不新增TaskStatus。检查管理与任务状态区分、成功/失败/运行的序列化、额外身份字段拒绝及contracts回归。消费方：v05-demo-reset-api/01。代码、协议验证、CI、真实页面与本人接受分别记录。
