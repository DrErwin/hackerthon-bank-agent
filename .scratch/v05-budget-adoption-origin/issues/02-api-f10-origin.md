# 02：原 F10 输入身份接入平台来源

Ticket ID: v05-budget-adoption-origin/02

Package: [v05-cross-linkage/packages/01-platform-bank：公共接缝与模拟银行](../../v05-cross-linkage/packages/01-platform-bank.md)

Spec: [预算采用来源最小设计](../spec.md)

Type: 开发（已确认拆分，实施等待前置）

Owner: Erwin

Directory: `backend/app/api/`

Status: blocked

Blocked by: [v05-budget-adoption-origin/01：平台可信来源与恢复](01-platform-origin.md) 提供稳定接口并实际合入；中控明确派发。

Planned execution thread: `01a171b0-4bf1-7571-bf2c-7c85c404329d`（原来源设计对话），GPT-6.1-sol/high。中控2026-10-25确认两票顺序；本票尚未进入编码，不与恢复503诊断混为一个API修复。

Core scenarios: O01—O08，定义见规格。

## What to build

既有 F10 请求体不变，仅专用预算候选选项路径保留原 request/interaction/option 并调用平台专用方法。聊天 provide_input 留在普通路径，不可借用来源。仅有原持久来源的精确中断请求可走受控恢复，不给所有 F10 放开重做。

## Acceptance criteria

- [ ] Cookie/同源、任务归属、原交互和选项检查保留；不接收 source=human、actor、plan_version 或候选摘要作为证明。
- [ ] 专用 F10 与模型续答的模块 response 即使相同，当前后台来源接口仍能区分；模型不能调用专用入口。
- [ ] 同号同参返回原 receipt，同号异参拒绝；同交互不同号不得重复采用。
- [ ] receipt 键不含 session 的既有事实不能扩大来源使用范围；原来源的主体/会话/轮次/任务另核验。
- [ ] 处理 accepted 前/后、completed 后/receipt 前断点；只恢复原来源和原结果，不重新生成来源、不用当前新任务结果替代原结果。
- [ ] 原 receipt/来源/attempt 历史核实在普通 current_input_task 之前严格分流；缺历史证据不绕过当前交互检查，已采用的补结果不重新授权。
- [ ] 普通 F10 金额/日期/配送及非预算输入继续原协议，确认/验证和未知银行动作不受影响。
- [ ] 与 cross06 接通后证明真实采用只发生于专用原 F10，缺来源的模型路径零 AdoptedBudget 写入；完整生日验收仍复用原 E2E 票。

## Verification

实施后通过 HTTP + 真实 Harness 验证 O01—O08。来源生成/恢复用真实持久记录，不以 monkeypatch source=true 代替；使用脚本 planner 证明模型知道全部选项也不能采用，另分层记录真实模型/页面验收。本轮只有当前缺口探针，不等于新接口已实现。
