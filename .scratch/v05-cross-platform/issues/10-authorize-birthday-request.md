# 10：authorize_birthday 回调透传请求参数

Ticket ID: v05-cross-platform/10

Package: [v05-cross-linkage/packages/01-platform-bank：公共接缝与模拟银行](../../v05-cross-linkage/packages/01-platform-bank.md)

Spec: [本工作组规格](../spec.md)

Type: 开发

Owner: Erwin

Directory: `backend/app/services/bank_gateway/`

Status: done — 2026-10-24 Erwin 批准合入，PR #273 squash 合入 main（`e8e2555`，先于 PR #272）；合并后 main 定向复测通过，安全侧释放载荷精确绑定随之生效。

Package accepted by: Erwin

Package accepted at: 2026-10-24

Execution assignee: ZCode 执行对话（Erwin 2026-10-24 指派）

Accepted by: 未记录（具体实施票）

Accepted at: 未记录

Planning approved by: Erwin，2026-10-24 裁定「可以可以，要看到这个金额信息」——银行放行回调须能看到本次提交的金额参数。只批准本票范围，不代表平台票 09 装配解锁。

Core scenarios: XL-B01、B05、X07；定义见[共享规格 §5](../../v05-cross-linkage/spec.md)。

## What to build

authorize_birthday 回调在现有（可信身份、操作编号、动作名）之外，第四参透传本次提交的类型化请求对象（FreezeFundsInput / CaptureFrozenInput / ReleaseFrozenInput / CreateOrderInput，均含金额与资源编号），供安全侧逐字段核对；默认拒绝与既有装配兼容性不变。

## Blocked by

无。

## Acceptance criteria

- [ ] 四个生日写动作（B10 冻结、B11 核销、B12 释放、B21 下单）的回调均收到本次请求对象，金额在回调处可见。
- [ ] 未装配回调仍默认 ACCESS_DENIED；回调返回 False 即拒绝且银行零写入。
- [ ] 既有 `lambda *_: True` 式回调与安全侧 authorize_birthday_write 三参调用不破坏。
- [ ] 网关目录测试覆盖：回调收到的就是本次请求（金额可断言）；回调拒绝时银行无写入。

## Verification

本票验证在 `backend/app/services/`：回调参数可见性与拒绝零写入用真实 MockBankService 断言；与安全侧的联合核对由 v05-cross-security/01 的测试在两票合入后自然覆盖（其回调用例已按第四参编写）。不涉及 agent_platform 装配（仍归票 09）。

## Delivery record

- 实现 / PR / 合入：分支 `feat/services/authorize-birthday-request`（基线 `fa40d45`，仅 `backend/app/services/bank_gateway/` + 同目录测试）：`_birthday_write` 增收 request 并透传给 authorize_birthday，B10/B11/B12/B21 四个写动作各自传入类型化请求。[PR #273](https://github.com/DrErwin/hackerthon-bank-agent/pull/273) 已于 2026-10-24 经 Erwin 批准 squash 合入 main（`e8e2555`）；CI 受 GitHub 账户计费阻塞（同 #268/#272，非代码原因，本地等价验证已记录）。
- 本票验证：2026-10-24，`backend/.venv`：`app/services/` 60 passed，新增 test_authorize_birthday_receives_the_typed_request（回调收到本次请求、金额可断言；拒绝路径银行零写入：冻结余额不变、bank_operations 仅剩已放行一条）。
- 组合预检：本地将本分支合入 PR #272 分支后同跑 `app/security/` + 网关生日套件，433 passed——网关四参回调与安全侧释放载荷精确绑定真实联动通过；两 PR 合入顺序任意（互为前向兼容），合入后精确绑定自动生效。
- 联合 E2E：不因本票单独通过。

## Comments

2026-10-24（来源）：v05-cross-security/01 审查时登记"网关 authorize_birthday 只传身份/编号/动作名"为接口现状；Erwin 当日裁定回调要能看到金额信息，安全侧先行支持 request 参数（PR #272，释放载荷精确核对、购买类仍由平台快照比对），本票补齐网关侧透传，合入后精确绑定自动生效。
