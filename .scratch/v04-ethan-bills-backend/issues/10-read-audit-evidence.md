# 10：只读审计证据收窄与真实持久化回归

Ticket ID: v04-ethan-bills-backend/10
Type: 返修
Owner: 周恩宇（Ethan / @zhouey314-cloud）
Directory: backend/app/modules/bills/
Status: resolved（PR #171 审计最小证据已合入，Issue #145 已关闭；历史数据清理/专业签核属于其它负责人）
Package: [v04-bills/packages/01-bills-backend：账单业务能力与评测](../../v04-bills/packages/01-bills-backend.md)
Spec: [本人实施规格](../spec.md)
Core scenarios: BF01/BF06 只读取数与可审计证据；不代替联合业务或专业安全验收
Verification: 测试实际持久化的 `audit_evidence`；started 为参数摘要，finished 为受控引用、状态和条数，禁止原始银行敏感字段；变异自证、bills/API 与完整后端结果如实记录。
Blocked by: 共享引用补丁 PR #153 已合入，新主线本分支全后端 701 项已通过；等待 PR 队列及后续审查，不再将首轮外部失败列为现行阻断。
Source issue: [Issue #145](https://github.com/DrErwin/hackerthon-bank-agent/issues/145)，依据 [Issue #137](https://github.com/DrErwin/hackerthon-bank-agent/issues/137) 的后续安全书面结论

## 问题与交付

账单只读路径的 `tool.started` / `tool.finished` 证据曾直接保存参数和银行响应；注释误称共享审计层会过滤银行事实。本票在 bills 调用侧生成最小证据，并修正该注释。

- `tool.started` 只提交共享 `parameter_digest` 计算的 `parameters_sha256`。
- `tool.finished` 只提交 `result_ref`、成功/失败 `status` 与 `row_count`；失败时条数未知为 `None`，附固定受控错误码，不把上游异常原样写入。
- 实际证据禁止原始 `counterparty_name`、`amount_fen`、`summary`、`transaction_id`、`available_balance_fen`。银行结果仍沿原受控调用返回，引用保留用户、任务、轮次范围，不自动展开完整响应。
- 只改 `backend/app/modules/bills/`，不修改共享安全、审计 writer、公共契约或历史审计数据。

## Comments

### 2026-10-19：实现与有效验证

- 基线 `9741053c304a194a4c3d5ab3048f4dbb8be3b0f9`；受测本地提交 `0ebfa54779ae6fd6f05d0b50028e6248144b5a91`，分支 `fix/bills/read-audit-evidence-145`。已推送远端 [bdb18abda3c0a19a5b3c08559d02f798c57b43b7](https://github.com/DrErwin/hackerthon-bank-agent/commit/bdb18abda3c0a19a5b3c08559d02f798c57b43b7)，两者 Git 树均为 `edce11331f71cdda0b0eaa9c7b69f42a70df3ef7`，代码工作树已对齐且干净。变更为 `reads.py`、`test_public_integration.py` 和 README；尚未新开 PR，不夹带其他目录。
- 两个新测试读取真实 SQLite `audit_evidence`，使用仓库 Harness、scoped saver、SecurityGate、BankGateway 和种子 Mock Bank；规划器与风险判断仍是明确测试替身。测试直接检查持久化字段、参数摘要、成功记录数、失败未知记录数及用户/任务/轮次范围。
- 在 backend 执行 `python -m pytest -q app/modules/bills/test_public_integration.py -k read_audit`：修复前 2 个测试变红，修复后 **2 passed, 8 deselected in 2.19s**。
- `python -m pytest -q app/modules/bills`：**161 passed in 3.15s**；`python -m pytest -q app/modules/bills app/api`：**237 passed in 68.85s**。`git diff --check` 通过，提交后代码工作树干净。
- API 测试环境原先禁止本地 `socketpair.send`，导致 AnyIO 跨线程唤醒停滞；未改动的基线同样复现。允许本地 socket/thread 通信后原始测试正常执行；未改依赖、未 monkeypatch AnyIO、未跳过测试。

### 2026-10-19：三个独立变异

每次只实施一个变异，执行上述 `-k read_audit` 命令，再恢复源码。恢复后 `reads.py` SHA256 为 `1124a2eafbac52b826a58d205de6a9807ce352a5de21efaa8d9b27f541ada39b`。

| 变异 | 实际结果 | 结论 |
|---|---|---|
| 恢复原始参数证据 | 1 failed, 1 passed, 8 deselected in 1.91s | killed |
| 恢复完整成功银行响应 | 2 failed, 8 deselected in 1.89s | killed |
| 将失败未知条数误记为 0 | 1 failed, 1 passed, 8 deselected in 2.18s | killed |

合计 **3 个独立 mutant killed、0 survived**。测试失败次数不作为变异数量；所有变异均已恢复，不进入提交。

### 2026-10-19：全后端失败与共享依赖对照

- 根执行者实际全后端结果为 **699 passed / 1 failed**。失败用例是订阅模块 `test_changed_bank_facts_cannot_reuse_the_answered_confirmation`，首次任务因 `SecurityError` 进入 `FAILED`。原结果保留，本票不能标记整仓全绿。
- Erwin 的 [PR #153](https://github.com/DrErwin/hackerthon-bank-agent/pull/153) 说明共享 `AuditJournal` 数字掩码可能随机改变不透明的 `*_ref` / `*_refs`。引用保护由共享底座工作线处理；此处保留当前失败，不越界顺手修改底座。
- 根执行者另在本地合成 /09 + L03 + #145 验证树，以 PR #153 的精确新增 `test_journal.py` 回归测试原 main journal：**1 failed**，`snapshot is not referenced by event`；只换为 PR #153 的精确 journal 后 **1 passed**。同一合成树 + PR #153 再跑原失败订阅用例及全 bills：**212 passed in 4.68s**。共享补丁只用于隔离验证，没有进入本票交付分支。
- 上述对照支持主线同类引用缺陷的依赖解释；原失败临时数据库已不可再读，未断言已还原那次失败的完整因果。212 项组合结果不是本票原分支的完整后端通过数，也不覆盖随后 L02 增量。
- `parameters_sha256` 中的连续数字仍可能被共享 `redact` 遮罩。本票测试按共享 `redact(parameter_digest)` 的实际持久化结果断言，与既有 transfer 路径一致；PR #153 的引用保护不等于该摘要遮罩限制也已修复。
- 237 项 bills + API 回归与上述全量失败并列保留；独立代码审查、Ringo 专业签核、该版本远端 CI 和最终合入各自记录。本票保持 `in_progress`，不关闭 Issue #145。

### 2026-10-19 后续：PR #153 已合入，新主线本分支回归通过

- Erwin 已正式合入 PR #153，main 为 [cd7c91ad80652852bb10fef139c2442d756ef359](https://github.com/DrErwin/hackerthon-bank-agent/commit/cd7c91ad80652852bb10fef139c2442d756ef359)。上游仅修改 journal 及其测试两份审计文件；本票随后 rebase 继承上游，仍只交付 bills 自有增量。
- 根执行者基于新 main 在本票真实分支受测源码 `1d572f4cf2d9fb02dbb26cfee4b35026dc0d98ac` 全后端实际得到 **701 passed in 126.08s**。先前 **699 passed / 1 failed** 留作历史，不再是现行外部阻断；历史 212 项合成验证不替代这一轮真实分支结果。
- 最新远端 [e6caabe43b981257e58bb5b2905ecff4602daf70](https://github.com/DrErwin/hackerthon-bank-agent/commit/e6caabe43b981257e58bb5b2905ecff4602daf70) 已推送；与受测源码 Git 树均为 `8b96c29cff3a783b333533e9d1e1678d45952f32`，已逐一核对。等待 PR 队列与后续审查，未记录为已合入或关闭。
- PR #153 只保护不透明引用，`parameters_sha256` 仍可能受数字掩码影响；这项边界保留，不因上游合入而改写成摘要保存完全正常。

### 2026-10-20 晚最终完成记录

[PR #171](https://github.com/DrErwin/hackerthon-bank-agent/pull/171) 已合入，Issue #145 已关闭；读取 started/finished 的新增 `audit_evidence` 不再落完整银行流水或余额。独立复查 SQLite 33个商户/摘要、39个银行引用等敏感内容命中0；后端 784+MockBank 14 passed。共享 AuditJournal 可能遮盖无盐哈希中的长数字，README 已按实际行为修正；历史已落盘审计记录如何迁移/清理及真人安全签核另归 Erwin/Ringo，不是本票未交付的模块修复。
