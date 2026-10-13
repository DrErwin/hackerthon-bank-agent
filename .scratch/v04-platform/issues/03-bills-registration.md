# 03：账单能力注册与意图路由（agent_platform）

Ticket ID: v04-platform/03
Type: 开发
Owner: Erwin
Directory: backend/app/agent_platform/
Status: resolved（[PR #117](https://github.com/DrErwin/hackerthon-bank-agent/pull/117) squash `f40959e` 合入 main，2026-10-13，含审查修复 `56406bf`：清单内重名能力拒绝注册〔契约 §6.9〕+ L02 输出 ref 待解析如实标注；独立子代理审查可合并〔AI 审查、非真人，意见见 PR 评论〕；合入后主线后端全量 431 passed）
Package: [v04-platform/packages/01-foundation-agent-mockbank：v0.4 底座、Agent 与模拟银行](../packages/01-foundation-agent-mockbank.md)
Spec: [v04-platform 场景规格](../spec.md)
Core scenarios: [P01 账单任务在平台上创建（能力注册与路由部分）](../spec.md)、P02（`module` 承载的前置）
Verification: `backend/` 下运行 agent_platform 测试：注册表完整性（缺字段拒绝注册）、意图路由选择账单能力、stub 往返、转账注册与路由回归不受影响。局部验收 = 注册与路由可用；P01/P02 场景通过以票 04 接线后的 E2E 为准。命令与输出记入本票 Comments。
Blocked by: None（跨线等 [v04-bills/01](../../v04-bills/packages/01-bills-backend.md) 公开能力（L01—L03）形态；未冻结时用契约形状 stub 先行，不构成实施前置）
Source issue: [Issue #87](https://github.com/DrErwin/hackerthon-bank-agent/issues/87)

## 交付

1. 账单模块注册：`ModuleManifest` + L01（summarize）/ L02（detect_anomalies）/ L03（generate_report）的 `CapabilityDefinition`（权限、敏感等级、副作用声明、超时、重试、handler 引用），把现有 `registry.register_transfer` 旁的注册点扩展为通用模块注册，不复制转账运行体系、不新建第二套底座。
2. 意图路由：规划入口按意图选择账单能力（复用既有 Harness / 规划入口；模型只动嘴，执行权在确定性代码）。
3. 模块应用工厂：提供转账 `TransferRuntime` 之外的模块级挂载接口，供票 04 在 api 层挂载账单运行时。
4. stub 工厂：账单公开能力形态未冻结时，用符合冻结契约形状的 stub 验证注册与路由（公共依赖未就绪时允许 stub，不复制公共实现）。

## 边界与依赖

- 不在本票：HTTP 任务视图 / 事件 / 载荷接线（票 04）；账单业务实现与评测（周恩宇，[v04-bills/01](../../v04-bills/packages/01-bills-backend.md)）；模拟银行接缝与种子（按需另开票）。

## Comments

- 2026-10-13：双轴审核通过后建立（原包建议 03 的 agent_platform 半张，按一票一目录拆出）。
- 2026-10-13 实施（分支 `v04-platform-03-bills-registration`，基于 main，先红后绿）：`registry.register_module`（模块前缀 / 唯一 / 非空校验）+ `public_catalog` 按能力声明 schema ref；`TransferProposal.capability_name` 放开为任意已注册能力名（注册表 + 授权回调仍是闸门）；harness 三处授权按快照 `capability_name` 取；新增 `bills_stub.py`（契约 §5.3 形状 L01—L03，只读零银行零模型，真实业务由账单模块替换工厂）与 `test_bills_registration.py` 三项。`agent_platform` 117 passed、后端全量 421 passed、转账回归不受影响。[PR #117](https://github.com/DrErwin/hackerthon-bank-agent/pull/117) 待统一审查。
