# 黑客松 Demo 连续办理与安全修复

Status: in_progress
Owner: Erwin（用户授权 AI 按票代行，长期目录归属不变）
Accepted at: 2026-10-22
Source issue: [Issue #227](https://github.com/DrErwin/hackerthon-bank-agent/issues/227)
Package: [bank-e2e-remediation/packages/01-demo-remediation](packages/01-demo-remediation.md)

## Problem Statement
交接报告 P0-1～P0-5、P1-6～P1-10：补充后不能继续、修改取消后断路、订阅缺验证码入口、求助误拦、风险依赖固定样例，以及查询/卡片/失败体验缺口。以 0263f4c 核对，后续输出凭据观察改动未解决这些入口问题。

## Solution
先让用户通过卡片与文字完成原任务，再接自然语言续办与风险判断。按单目录分票，优先验证每次变化是否产生正确的新确认与银行结果。首批 01→02 交付可填写/可修改转账路径；随后 03～07 补齐订阅和安全链，08～10 补查询与业务卡片，11 验收。

## User Stories / Core scenarios
1. S01：用户发起转账、查本人账户和联系人、补金额或付款账户，始终继续选中的任务；多个任务先明确选择。
2. S02：提交前修改金额、收款人或账户，未改内容保留，旧确认失效，新内容必须重新确认；提交后只能查原结果。
3. S03：盘点订阅，区分签约/疑似/已退订，选择单项退订、确认、专用验证码验证、回执。
4. S04：讨论有人索要验证码可得到帮助；实际验证码/密码不进聊天记录和模型。
5. S05：正常转账、共享屏幕/保密/催促等风险成对判断；未知及检测失败不默认允许。
6. S06：账单选范围、分类明细和陌生扣款追问继承范围；不能支持的范围用普通话说明并给替代。
7. S07：取消、刷新、失败和重复提交保留任务身份；实际银行动作不重复。
8. S08：用户知道还在处理、已失败或结果待核实；语音若为固定示例必须明确，不冒充真实识别。

## Implementation Decisions
- 复用原任务 fields 更新、确认版本和操作编号，不通过取消后重发 prompt 模拟修改。
- 新草稿入口为兼容扩展，绑定 task_revision；仅允许未提交且等待确认的普通转账。等待输入阶段使用 F10，新增权限不由前端决定。
- 自然语言只提出续办候选，由 API/业务模块检查归属、版本、等待动作；确认与验证码专用入口不变。
- 风险检测是证据，不是执行权；普通 demo 参数范围须有明确服务端事实，固定场景不能覆盖文本危险线索。
- 用户允许必要时尝试 TypeSafe AI/Jev；不预设选型，不复制密钥。先利用现有 56 条样例，不重复建数据集。
- 本轮按用户“开始改造、按优先级拆票实施”的直接授权执行，无需重复询问规划粒度。代码合并仍保留仓库安全审查边界。

## Testing Decisions
既有 HTTP TestClient 接真实转账图、安全门及隔离模拟银行；模型替身仅验证程序。对关键缺陷先写失败回归再实现，核对银行操作数、旧确认拒绝与幂等。前端组件测试覆盖提交与失败，真实 React+真实模型验收另行记录。每票局部通过不等于 S01～S08 全部通过。

## Out of Scope
生产银行、部署、完整多用户产品、全部赛事场景、全新语音服务、视觉重设计、无依据的模型选型和专业安全认证。原诊断中的长诈骗 MODEL_UNDERSTANDING_FAILED 保留，不能用离线样例覆盖。

## Further Notes
2026-10-22 已读本机 to-spec/to-tickets/implement/code-review；前三项带 disable-model-invocation，未声称通过不存在的命令调用，按仓库授权的同名流程手工执行。方案来自用户已明确范围与既有报告。仅代码审查按 code-review 使用两轴独立审查。不得触碰主工作区 showcase 未跟踪内容。未同步飞书。

## Tickets

| 票 | 优先级 | 交付 | 目录 | 依赖 |
|---|---|---|---|---|
| [01](issues/01-draft-api.md) | P0 | 原任务补充与转账草稿修改入口 | `backend/app/api/` | 无 |
| [02](issues/02-interactive-cards.md) | P0 | 可填写、可修改的卡片及可靠等待反馈 | `frontend/` | 01 |
| [03](issues/03-subscription-verification.md) | P0 | 退订验证动作与清单事实修复 | `backend/app/modules/subscription/` | 无 |
| [04](issues/04-conversation-planning.md) | P0 | 自然语言续办与安全求助的模型入口 | `backend/app/agent_platform/` | 无 |
| [05](issues/05-conversation-dispatch.md) | P0 | 聊天续办可靠派发与隐私前置过滤 | `backend/app/api/` | 04 |
| [06](issues/06-text-risk-policy.md) | P0 | 对话风险证据的确定性兜底 | `backend/app/security/` | 无 |
| [07](issues/07-risk-wiring.md) | P0 | 风险输入接线与可办理 Demo 参数范围 | `backend/app/agent_platform/` | 06 |
| [08](issues/08-own-bank-queries.md) | P1 | 本人账户余额和联系人只读能力 | `backend/app/agent_platform/` | 无 |
| [09](issues/09-bills-followup.md) | P1 | 账单范围与明细续查 | `backend/app/modules/bills/` | 04 |
| [10](issues/10-business-cards.md) | P1 | 账户与订阅逐项卡片和账单明细操作 | `frontend/` | 02,03,05,08,09 |
| [11](issues/11-acceptance.md) | P0/P1 | 三条真实用户路径联调与安全复验 | `evals/demo-remediation/` | 01,02,03,04,05,06,07,08,09,10 |
