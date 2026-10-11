# v04-bills-bank-seam/04：本机演示启用共用种子流水

Ticket ID: v04-bills-bank-seam/04
Package: PM 自拆（不开交付包）；Source issue [Issue #91](https://github.com/DrErwin/hackerthon-bank-agent/issues/91)
Spec: [v04-bills-bank-seam 规格](../spec.md)
Core scenarios: BF01/BF03/BF05/BF06 在本机演示里能查到真实月份流水（前端与账单侧联调才有数据）
Verification: `python -m pytest -q app/agent_platform/`（backend/ 下）全绿；测试从演示启动链路进入，经 `BankGateway.list_transactions` 读到当前月与上月样本；未启用时既有演示行为不变
Owner: Erwin
Directory: `backend/app/agent_platform/`
Status: open
Blocked by: [v04-bills-bank-seam/02：银行接缝 list_transactions](02-bank-seam-list-transactions.md)
Source issue: [Issue #91](https://github.com/DrErwin/hackerthon-bank-agent/issues/91)

## What to build

票 03 给了账本事实列与种子写入机制、票 02 给了 B08 查询与种子数据，但本机演示（`local_demo.py`）默认不种流水，账单场景仍看到空数据。本票把演示链路接上：

1. `agent_platform/local_demo.py` 在建好模拟银行后调用票 02 的种子流水入口（时钟走银行自己的 `_now()`，与本机演示的启动逻辑一致）。
2. 测试（沿用 `test_local_demo.py` 的演示启动链路）：启动后从 `BankGateway.list_transactions` 能读到当前月与上月的样本流水；重复启动不重复种。

## 实现要点

- 只做"启用"：不新增种子内容、不改 B08 语义、不动演示的账户 / 记忆 / 安全预置。
- 测试默认不种流水（沿用票 03 的边界），避免既有 `list_ledger` 断言语义变化。
- 本机演示的数据库若来自旧版本，迁移与播种都要幂等，不因重复启动报错。

## Acceptance criteria

- [ ] 本机演示启动后有共用种子流水，`BankGateway.list_transactions` 可查到当前月与上月样本
- [ ] 重复启动幂等，不重复写入、不报错
- [ ] 未调用播种入口的既有测试路径行为不变
- [ ] `python -m pytest -q app/agent_platform/` 全绿、后端全量无回归；PR 合入、CI 通过
