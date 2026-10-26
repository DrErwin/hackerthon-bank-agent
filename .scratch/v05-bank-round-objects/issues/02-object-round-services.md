# 02：银行服务与网关按可信轮次校验冻结/订单对象

Ticket ID: v05-bank-round-objects/02

Package: [v05-cross-linkage/packages/01-platform-bank：公共接缝与模拟银行](../../v05-cross-linkage/packages/01-platform-bank.md)

Spec: [本工作组规格](../spec.md)；责任判断与证据见[核查报告](../verification.md)。

Type: 开发

Core scenarios: 不适用（存储/服务基础设施票；对应验收见[包 06](../../v05-cross-linkage/packages/06-bank-eval.md)验收第 4 条与 [v05-cross-bank-eval/02](../../v05-cross-bank-eval/issues/02-round-object-regression.md)）。

Owner: Erwin（v0.5 统一承担）

Directory: `backend/app/services/`

Status: done — 2026-10-26 已 squash 合入 main `b63ec1b`（PR #316）；双轴必须项已闭合；CI 计费未启动记 Blocked。评测 02 已随后合入 `5b4b99d`，跨轮红灯窗口归零。

Blocked by: [v05-bank-round-objects/01：存储层对象轮次归属](01-object-round-storage.md)（实施依赖）。

Start when: Owner 已确认（见 [spec 背景](../spec.md)）、01 合入并取得 `backend/app/services/` 单目录窗口（生日系列 §4 第 4 条可能新增 services 票，按“生日需要的目录先完成”排队）。

## What to build

1. `MockBirthdayBank` 写路径把本次可信上下文 `demo_round_id` 传给存储原子提交（`freeze_funds`、`create_order`、`capture_frozen`、`release_frozen`），生产写入始终带轮次：
   - 冻结/订单创建写入归属轮次；
   - 核销/释放/订单付款关联由存储校验同轮次。
2. 对象读取按可信上下文轮次校验：
   - `get_freeze` / `get_order` 增加可选 `demo_round_id` 服务参数；网关 `BankGateway.get_freeze` / `get_order` 传 `context.demo_round_id`；
   - **先按 user 取整行、再比较轮次**（不把轮次下推存储过滤）；对象不存在 → `RECORD_NOT_FOUND`；存在但归属其他轮次 → `ACCESS_DENIED`；同轮次返回原视图。
   - 直接以旧参数调用（无轮次）只保留给既有测试装配，生产网关路径不得出现（测试可断言网关一定传轮次）。
3. 写路径前置校验：`_freeze_row`、`capture_frozen`、`release_frozen` 及 `capture_frozen` 关联的订单都按当前轮次校验；跨轮在调用存储前返回明确 `ACCESS_DENIED` 失败回执（不得落到存储 `ValueError` 再被网关映射成 `OPERATION_CONFLICT`）。禁止用 `OPERATION_CONFLICT` 表示跨轮拒绝。
4. 启动收口：`MockBankService` 初始化时检查银行库冻结/订单对象是否存在无轮次行（`demo_round_id IS NULL`）；存在则明确 `RuntimeError` 拒绝加载并提示保留原库/启用新库（镜像 `core.py:103-110` 对无 scope 旧操作的先例），避免冻结余额被 NULL 行卡死且无法释放。该检查应在 `seed_demo`/`seed_subscriptions` 等种子写入**之前**执行；若实现顺序无法前置，须证明种子幂等且不新增/覆盖冻结/订单对象行，验收以对象行与 `user_version` 不被改写为准（不承诺整个数据库文件逐字节不变）。
5. 同轮正常路径保持不变：B10→B21→B11→B12、B14 原操作回查、响应丢失后原编号恢复、订单只付一次、释放余额按银行事实。
6. 更新 `backend/app/services/mock_bank/README.md`：B10—B13/B20—B22 的轮次归属、错误码与拒绝语义；`bank_operation_scopes` 与对象归属的关系；02 启动拒绝 NULL 对象的边界。

## Acceptance criteria

- [ ] 网关在真实授权回调下，D2 对 D1 冻结/订单的 B13/B22 读取返回 `ACCESS_DENIED`；同轮读取仍成功；缺失对象仍 `RECORD_NOT_FOUND`。
- [ ] D2 用新编号核销/释放 D1 冻结：返回 `ACCESS_DENIED` 失败回执，无资金/冻结/订单/付款关联变化，不产生成功回执；**不接受 `OPERATION_CONFLICT`**；同轮正常核销/释放/付款保持通过。
- [ ] D2 创建订单带 D1 `order_id` 付款：拒绝 `ACCESS_DENIED`；同轮合法订单付款一次，重复执行只观察原操作。
- [ ] 银行库存在无轮次对象行时启动拒绝加载，且冻结/订单对象行与 `user_version` 不被改写（允许既有幂等种子重复写入）；正常库启动不受影响。
- [ ] 缺省无轮次的直接调用（既有测试/内部装配）行为不变；新增回归断言：生产网关 `get_freeze`/`get_order` 必然传 `context.demo_round_id`（防永久 fail-open）。`app/security/test_birthday_release.py:716` 等直接 `birthday.get_freeze("U1", …)` 调用列入兼容白名单，不为此改 security 文件。
- [ ] 只改 `backend/app/services/`；不触碰 security/agent_platform/storage/evals，不改公共契约字段，不新增业务规则。
- [ ] 修复后 `evals/mockbank/test_birthday_bank_eval.py` 的四项 strict xfail 预期 XPASS；须先备好 [v05-cross-bank-eval/02](../../v05-cross-bank-eval/issues/02-round-object-regression.md)，按 01→02→评测 02 相邻合入，或由中控记录接受红灯窗口；本票不修改评测期望。

## Verification

从 `backend/` 运行隔离临时库验证：

```powershell
$env:PYTHONPATH=(Get-Location).Path
python -m pytest -q app/services/ app/security/test_birthday_release.py --basetemp=<本票独立临时目录>
```

`app/security/test_birthday_release.py` 只读运行以确认释放收尾未被破坏，不改 security 文件、不纳入本票交付物；若确有跨目录问题交回安全/中控，不越界修复。真实 claim/执行器与银行局部装配验证可供评测票复用；不启动模型、HTTP 或页面。代码完成后两位独立子代理规范/规格审查、必须项闭合、单独 PR 回交，不自行合并；按 [spec 约束](../spec.md) 记录安全审阅（Erwin 代行或 Owner 判定不构成新安全规则），不写 Ringo 签核。

## Delivery record

### 2026-10-26 实施

- 分支/worktree：`codex/v05-bank-round-objects-02`，独立 worktree `C:/Users/57652/.codex/worktrees/v05-bank-round/hackerthon-bank-agent`；基线 main `aa41df5`（01 storage 已合入 `819bbfb`）。
- 实施内容：`MockBirthdayBank` 写路径（冻结/下单/核销/释放）把 `context.demo_round_id` 传给存储原子提交；`_freeze_row` 按用户取行后比较轮次，跨轮返回 `ACCESS_DENIED` 失败回执，核销携带的订单同样校验；`get_freeze`/`get_order` 增可选轮次并区分 `RECORD_NOT_FOUND`/`ACCESS_DENIED`；网关固定传可信轮次；`MockBankService` 启动拒绝无轮次对象行；更新 `services/mock_bank/README.md`（含 operation scope 与对象轮次两层关系）。
- 本票验证（隔离临时目录，cwd=本 worktree `backend/`）：
  - `app/services/test_birthday_bank.py` → **13 passed**（跨轮读取/核销/释放拒绝、跨轮订单拒绝、启动 NULL 拒绝并断言对象行/user_version/accounts 不变、网关传轮次、缺失对象 `RECORD_NOT_FOUND`）；
  - `app/services app/security/test_birthday_release.py app/agent_platform/test_birthday_order_scope.py app/agent_platform/test_birthday_runtime_wiring.py` → **126 passed**；
  - `../evals/mockbank/test_birthday_bank_eval.py` → **4 failed, 37 passed**（四项 strict xfail 按设计 XPASS）；`../evals/mockbank` 全目录为 **5 failed, 53 passed**：第 5 项是 `test_birthday_round_attribution.py::test_current_task_rejects_old_order_and_pays_its_own_order`（D2 用网关读 D1 旧对象，现被 `ACCESS_DENIED`）。两项均由 [v05-cross-bank-eval/02：跨轮次旧对象边界回归收口](../../v05-cross-bank-eval/issues/02-round-object-regression.md) 转正；02 合入到评测票合入之间 `evals/mockbank` 为 5 项红灯窗口，中控须按该口径记录，不能只写“四项立即转正”。本票不改评测期望。
- 代码审查：规范轴/规格轴两位独立子代理已完成；发现并已修复：启动 NULL 测试假阳性（补 scope 行与行/user_version/accounts 断言、参数化 freezes/orders）、跨轮断言补 order_payments/ledger/released_total、补 get_order 缺失对象、README 补 operation scope 关系、get_freeze/get_order docstring。修后复跑上述 13/126 通过。
- 安全审阅：本票新增银行对象访问拒绝判定，按 AGENTS.md 属资金执行链路的安全相关改动；v0.5 阶段由 Erwin 代行审阅并如实记录为代行（不写 Ringo 签核）；PM 2026-10-26 16:10「把这些都做了吧」授权继续推进。
- PR：[#316](https://github.com/DrErwin/hackerthon-bank-agent/pull/316)，head `bf8f592`，**已 squash 合入 main `b63ec1b`**（2026-10-26 16:56）；评测 02 随后合入 `5b4b99d`，本票造成的 5 项红灯窗口归零。CI [Repository checks](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/40291651775/job/121467880318) 结论 failure，annotation 明确“job was not started because recent account payments have failed…”，job 未运行、无测试证据，不记 CI 绿、非测试失败。
