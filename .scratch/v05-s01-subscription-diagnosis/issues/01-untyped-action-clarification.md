# 01：明确单项停止扣费不得静默降级为盘点

Ticket ID: v05-s01-subscription-diagnosis/01
Package: [v05-cross-linkage/packages/05-cross-e2e：联动E2E](../../v05-cross-linkage/packages/05-cross-e2e.md)（仅来源关联，不表示实施包已激活）
Spec: [正式实施规格](../spec.md)；[原诊断](../diagnosis.md)
PR: [PR #304](https://github.com/DrErwin/hackerthon-bank-agent/pull/304)（draft，未合并）
Source issue: [Issue #302](https://github.com/DrErwin/hackerthon-bank-agent/issues/302)；原完整S01另属Issue #301
Type: 开发
Owner: Erwin
Directory: `backend/app/modules/subscription/`
Status: in_review — 开发及132项定向验证、双轴独立AI复核完成；PR304草稿已回交，CI账单阻断，待中控审查
Blocked by: None；若需新平台信息，先回交平台提供方另票
Core scenarios: 明确单项停止未来扣费、明确只读、取消目标不明/多候选/批量；不替代XL-S01
Verification: 沿真实公开工厂使用隔离端口验证入口模式、消歧、确认/验证及零提前写入；修复后真实S01由原E2E线新批次另验

## 原问题与最小证据

固定PR300 head31e995e75c12af57e05ae8cc9cda56b3da2d9693，旧信封文本“请帮我停止优酷的自动扣费”经公开工厂实际返回list/succeeded且无交互；同文SubscriptionCancelInput先到confirmation，均fake写调用0。见诊断的10行离线观测及原SOP-2规定。证据仅Fake端口级，不是一次新的真实模型/银行失败。

## What to build

使明确单项停止未来扣费的意图不能因未命中既有词表就静默当成查询办结；仍先认清本人银行签约对象，对象不足或多候选要求选择，明确项最多先进入原确认/验证，不自动取消。

## 验收边界

- [x] 明确单项取消/停止未来扣费先认对象并沿原确认、基础身份验证及统一执行器；确认前零银行写。
- [x] 明确只读查询继续盘点成功；已明确取消但目标不明/多候选/批量继续WAITING_INPUT并逐项选择，不默认第一笔。
- [x] typed List/Cancel、既有旧信封正常路径、取消/幂等/拒绝/未知回查保持既有语义；模型capability和聊天文本均不作执行授权。
- [x] 不硬编码S01原句/商户，不拼个案prompt，不扩大#160、不改风险事实或银行/公共契约；实现保持KISS。
- [x] 只改subscription目录及本候选材料。完整生活目标的cross路由归原平台线，前端/平台/安全/银行缺口分别回交，不跨目录修。
- [x] 实施若需新增入口绑定语义/平台字段，先提交具体方案与目录依赖，不自行裁定不确定表达的产品规则。
- [x] 实施后独立规范/规格审查均PASS，单目录代码PR回交中控；表示本地开发验证完成，不表示合入或E2E接受。

## 执行领取

Accepted by: Erwin授权Codex（中控正式分派）
Accepted at: 2026-10-25
Directory: backend/app/modules/subscription/

从最新origin/main 855497fa16616595eac8cfac9013ec701ffe942d建立独立managed worktree；只携入74da8d9本组材料，不携入PR300观察器/祖先提交。实施遵循已读implement/TDD流程；implement文件未注册为当前会话可调用技能，按文件流程执行，不冒称已调用。用户已明确公开工厂测试接缝，先保留失败回归再修复。当前仅行为解析修复，不扩平台契约/安全决策；不跑无关全量或真实模型。

## 开发交付

当前132项定向回归通过，Standards/Spec独立AI审查分别PASS、剩余必须项0；详见[实施证据](../implementation.md)、[独立报告](../review.md)与[后续E2E方案](../e2e-acceptance-plan.md)。实际E2E未执行，回交后停止；不关闭301/S01，不自行合并或沿用旧CI例外。

交付PR：[PR #304](https://github.com/DrErwin/hackerthon-bank-agent/pull/304)。base `1b3afec5336e5906f87259c7b1c903823cc574e1`，分支 `codex/v05-subscription-stop-intent`。首次CI在head `ce6eb32ec8c0aa685502760ec97b4ce026c38c3f` 因GitHub账单/消费额度而未启动；不是CI通过，也不是本票已获豁免。负责人后续决定CI处置及合入，开发回交后停止。
