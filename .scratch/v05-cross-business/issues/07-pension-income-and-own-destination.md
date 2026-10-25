# 07：养老金真实入账识别与本人账户去向

Ticket ID: v05-cross-business/07

Package: [v05-cross-linkage/packages/03-cross：三个生活目标编排](../../v05-cross-linkage/packages/03-cross.md)

Spec: [本票规格](../pension-input-fixes-spec.md)

Type: 开发

Owner: Erwin（授权执行对话代行）

Directory: `backend/app/modules/cross/`

Status: implemented / integration_blocked — 2026-10-25 实现及双轴复审通过，Draft PR #297待中控按284/292依赖排序；完整E2E及风险事实仍未接受。

Accepted by: Erwin（授权执行对话代行）

Accepted at: 2026-10-25

Core scenarios: XL-P01/P02/P03，回归 XL-P04—P06、XL-X02—X05。

Blocked by: 实施无新增业务裁定；完整真实账单装配/可合并交付依赖
[PR #284](https://github.com/DrErwin/hackerthon-bank-agent/pull/284) 与
[PR #292](https://github.com/DrErwin/hackerthon-bank-agent/pull/292)，未合时仅隔离组合验证。
风险/参数事实由原安全平台线承担，不在本票代填；未知保持暂停。

## What to build

识别合法真实入账；让用户选择真实本人储蓄账户或家人联系人。只走原公开查询和转账入口，
不以余额冒充养老金、不把A5伪造成联系人，不改变风险语义。

## Acceptance criteria

- [x] direction=inflow、nature=transfer 的当前账户流水能被选择；真实交易编号/金额进入来源记录。
- [x] 多笔入账先由用户选定，不自动认全部为养老金；退款/利息/转出/其他账户不混入。
- [x] 本人A5可读可选，即使不在payees；排除付款自身账户，保留家人SavedPayee。
- [x] OwnPayee/SavedPayee及金额通过公开派发传递，不复制转账内部规则，不降低确认/验证要求。
- [x] 查询失败、旧选项、未知、取消及原养老金留存/D1回归不退化；未变风险配置/夹具。
- [x] 契约测试、真实公开能力与284/292组合证据分层记录，两轴子代理必须项清零。

## Verification / Delivery record

按PI01—PI06及现有养老金测试验证，先复现后最小修复；完整E2E仍归
[v05-cross-e2e/02](../../v05-cross-e2e/issues/02-monthly-arrangement-e2e.md)。
已交 [Draft PR #297](https://github.com/DrErwin/hackerthon-bank-agent/pull/297)，未合并。
首次实现后端全量1591 passed（13m38s），审查回修后的最终Cross48 passed；组合52 passed，
MockBank14 passed；Spec独立用例/组合探针各1 passed。双轴复审PASS，原1项P2已修。
CI账户计费导致job未启动，不记为绿；实际转账仍因安全核对未完成暂停、零资金写入。
完整记录见[本票交接](../review-07.md)。未代签真人安全或PM验收。
