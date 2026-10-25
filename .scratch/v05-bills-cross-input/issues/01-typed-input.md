# 01：账单公开工厂接收类型化输入

Ticket ID: v05-bills-cross-input/01
Package: [v05-cross-linkage/packages/01-platform-bank：公共接缝与模拟银行](../../v05-cross-linkage/packages/01-platform-bank.md)
Spec: [账单类型化输入入口](../spec.md)
Type: 开发
Owner: Erwin
Directory: `backend/app/modules/bills/`
Status: in_progress
Blocked by: None（现行公共模型、PR #264 平台派发已合入）
Accepted by: Erwin 授权执行对话
Accepted at: 2026-10-25
Core scenarios: BI01—BI06，见 spec
Verification: 公开工厂精确保留结构化参数；真实 Harness + 安全门 + 隔离种子银行验证实际依据及零写入；覆盖拒绝、重试、恢复及旧聊天回归。

## Acceptance criteria

- [ ] 三种输入分别经各自注册工厂运行，summary/details/comparison、异常三模式、报告目的符合既有服务契约。
- [ ] 银行事实、读取权限、失败语义、原任务重试/恢复/重放未绕过。
- [ ] 普通聊天路径不回归，其他能力输入和裸字典拒绝。
- [ ] 独立子代理审查规范与原始规格，修复必须项，代码 PR 交中控排队合并。

## Delivery record

待验证；真实模型/HTTP/页面 E2E/真人接受未执行。
