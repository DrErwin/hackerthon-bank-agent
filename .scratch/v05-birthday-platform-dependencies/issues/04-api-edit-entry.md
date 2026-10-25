# 04：F10当前生日待办的受控编辑分流

Ticket ID: v05-birthday-platform-dependencies/04
Package: [v05-cross-linkage/packages/01-platform-bank：公共接缝与模拟银行](../../v05-cross-linkage/packages/01-platform-bank.md)
Spec: [平台提供条件及最小规格](../spec.md)
Type: 开发（本轮只规划，不实施）
Owner: Erwin（v0.5阶段统一负责）
Directory: `backend/app/api/`
Status: planned / blocked — 本轮无编码授权，不是ready-for-agent。
Planning assignee: Codex，01a1718a-26a3-7523-a0bf-2591d8e83618；2026-10-25。
Implementation assignee / accepted at: 未领取。
Blocked by: [本组03：原任务编辑交接](03-platform-edit-handoff.md)；规格G1按契约§8完成跨方确认并更新正式契约/必要模型示例；中控明确授权。与[v05-budget-adoption-origin/02：原F10输入身份接入平台来源](../../v05-budget-adoption-origin/issues/02-api-f10-origin.md)的同文件修改交中控顺序安排，不代做其能力，亦不冒称它是商品编辑的业务前置。
Core scenarios: P03/P04/P05/P06/P08；[P01—P08验证框架](../spec.md#6-testing-decisions只设计未运行)对应Cross08 Q01—Q10及XL-B01—B07。

## What to build

若G1获确认，复用F10已有请求字段，只有Cross当前confirmation/verification上后端发布的特定编辑选项可走平台03。
其他模块及普通input保持原行为；后续数量/商品输入仍由Cross08的F10处理。本票不放宽F15，也不扩大普通转账draft接口。

## Minimum input / output

输入为原request_id、interaction_id、selected_option_id，text为空；不得接受supplied source/actor/editable/operation/候选hash。
通过平台03完成撤离与检查点后输出同task_id的新waiting_input TaskView；未能证明未提交则输出原操作核实/拒绝，不先给成功编辑卡。
新分支改变F10状态语义，当前不可调用；若G1改用其他接口，先重修本票，不自行创造端点或模型字段。

## Acceptance criteria

- [ ] Cookie/同源/主体/会话/轮次/任务归属、当前交互及后端编辑选项映射在mutate路径核对。
- [ ] 新分支不调用旧动作resume来“尝试退出”，不以F15 cancel或转账draft当Cross修改；普通text/模型revise不能进入此分支。
- [ ] receipt保留同参重放和同号异参拒绝；已有持久撤离/编辑记录的精确原request才可受控恢复，全部F10不开放重试。
- [ ] 安全撤离成功但平台记录缺失的断点，可由平台按原request只读恢复；无持久事实不自动当新编辑请求。
- [ ] 旧确认/验证回调和旧交互不重新执行撤离动作；原先已发生事实如实保留，新卡按task_revision发布。
- [ ] 未知/claim先胜时沿原操作核实；新会话/终态不把旧receipt或来源当新写入权。
- [ ] 原F10输入、F15确认、验证码与普通转账/订阅调用兼容；无新SecurityDecision/状态枚举。
- [ ] 若公共模型确需变动，先回contracts提供目录；若平台能力未就绪保持blocked，不跨目录补。

## Verification / downstream

实施后以真实HTTP+平台03+安全02验证新分支、精确拒绝、重复/竞争/回执中断和原任务新input；原Cross08接线与页面E2E分别留证。
不提前实施预算来源API02/cross06、原前端02或总E2E03。本轮只文档核对，无测试/模型/CI。
