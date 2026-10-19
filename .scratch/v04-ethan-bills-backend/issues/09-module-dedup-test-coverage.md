# 09：模块防重用例补真实覆盖（杀变异 M2）

Ticket ID: v04-ethan-bills-backend/09
Type: 测试
Owner: 周恩宇（Ethan）
Directory: backend/app/modules/bills/
Status: in_progress
Package: [v04-bills/packages/01-bills-backend：v0.4 账单业务能力与评测](../../v04-bills/packages/01-bills-backend.md)
Spec: [v04-ethan-bills-backend 账单实施规格](../spec.md)
Core scenarios: BF01（同请求不重复读银行）；测试覆盖真实性返修
Verification: 新用例绕开平台短路（`harness.py:417-418` 同 request_id 短路）直接驱动模块入口，证明 `entry.py:160-161` 的模块级防重独立生效：同 `(session, request_id, intent)` 重放不再触发银行读取、返回同一结果；对防重判断做变异（删掉模块防重分支）用例必须变红。`app/modules/bills` 全量回归通过。命令与输出记入本票 Comments。
Blocked by: None
Source issue: [Issue #136](https://github.com/DrErwin/hackerthon-bank-agent/issues/136)

## 交付（对应 [Issue #136](https://github.com/DrErwin/hackerthon-bank-agent/issues/136) 清单项 4）

1. `test_public_integration.py:194-201` 的 `test_no_duplicate_reads_when_original_start_is_replayed` 用例名声称覆盖模块防重，实际由平台短路满足（变异 M2 存活）——补一条真正覆盖模块级防重（`entry.py:160-161`）的用例，或若平台短路即设计意图则改用例名并说明。
2. 变异自证：在票内 Comments 记录「改坏模块防重 → 新用例红」的证据（杀了几个、活了几个）。

## 边界与依赖

- 只改 `backend/app/modules/bills/` 测试（必要时含被测分支的最小修正）。
- 与 [08](08-l01-rework-consistency.md) 相互独立，可并行；同目录分支注意先后合入与 rebase。

## Comments

- 2026-10-16：PM 侧按 [PR #131 审查结论第四节](https://github.com/DrErwin/hackerthon-bank-agent/pull/131#issuecomment-6198615597) 第 4 项开票（[Issue #136](https://github.com/DrErwin/hackerthon-bank-agent/issues/136)），Owner 周恩宇接手实施。

### 2026-10-19：模块入口测试与 M2 变异自证

- 基线 `9741053c304a194a4c3d5ab3048f4dbb8be3b0f9`；完整受测提交 `407a72c5fa4517ab29886997b9d6984239ab6f7a`。仅改 bills 的测试和 README，生产防重逻辑不变。
- 新参数化测试 `test_module_start_replay_returns_saved_result_without_reads_or_checkpoints` 覆盖成功及等待账户选择两个状态。绕开 Harness，以新建模块实例、同一 saver 和同 `(session, request_id, intent)` 重放，确认银行调用与 checkpoint 写次数不增加，结果仅更新本轮 `run_id`。既有集成用例改名为 Harness 防重，避免冒称模块覆盖。
- 在 backend 实际运行 `python -m pytest -q app/modules/bills/test_public.py -k test_module_start_replay_returns_saved_result_without_reads_or_checkpoints`：独立复核 **2 passed, 54 deselected in 0.20s**。
- M2 只做一次独立变异：删除 `BillsEntry.start` 的已保存 `result` 返回分支，再执行上述命令。两个参数化测试均因额外银行读取而失败，实际 **2 failed in 0.16s**；随后完整恢复生产源码。正确统计为 **1 个 M2 mutant killed、0 survived，2 个测试变红**，不是 2 个 mutant。
- 根执行者完整后端回归 **700 passed in 131.64s**，Mock Bank **14 passed**；独立 Spec 复核未发现新增阻断项。结果对应上述完整受测提交，不移用其他分支测试数。
- 已实际更新原远端分支，head `e797a62e10ede3b4118a6f171daa6079bec8a640`；Git 树 `32183611758125e03921aa67907dc06eb5c753af` 与受测 `407a72c` 完全相同。当前同时最多两个未合 PR，未另开第三个 PR；本票保持 `in_progress`，远端分支已更新不等于 PR 已提交、已审查或已合入。

### 2026-10-19 后续：新主线本分支回归通过

- 同步 PR #153 合入后的 main `cd7c91ad80652852bb10fef139c2442d756ef359`，受测源码 `74350ce9766e1df0e566de4ac804f2fd7f9081be`；根执行者在本分支全后端实跑 **701 passed in 125.32s**。
- 最终远端 [38aa8de1063b90462582346d18076761ace59792](https://github.com/DrErwin/hackerthon-bank-agent/commit/38aa8de1063b90462582346d18076761ace59792) 已推送，与受测源码 Git 树均为 `8445f1ada8e3f2089c4bda22020a14446b96f3aa`。前序 407a72c/e797a62 与 700/14 的结果保留为历史。
- M2 仍是 **1 个独立变异 killed、0 survived、2 个测试变红**；新主线多出的测试不改变该变异统计。本票继续 `in_progress`，尚未为本分支新开第三个 PR，待队列与审查/合入。
