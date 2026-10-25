# 02：银行服务与网关按可信轮次校验冻结/订单对象

Ticket ID: v05-bank-round-objects/02

Package: [v05-cross-linkage/packages/01-platform-bank：公共接缝与模拟银行](../../v05-cross-linkage/packages/01-platform-bank.md)

Spec: [本工作组规格](../spec.md)；责任判断与证据见[核查报告](../verification.md)。

Type: 开发

Core scenarios: 不适用（存储/服务基础设施票；对应验收见[包 06](../../v05-cross-linkage/packages/06-bank-eval.md)验收第 4 条与 [v05-cross-bank-eval/02](../../v05-cross-bank-eval/issues/02-round-object-regression.md)）。

Owner: Erwin（v0.5 统一承担）

Directory: `backend/app/services/`

Status: blocked — 待 Owner 确认防御纵深决策、01 合入及 `backend/app/services/` 目录窗口；未实施。

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
4. 启动收口：`MockBankService` 初始化时检查银行库冻结/订单对象是否存在无轮次行（`demo_round_id IS NULL`）；存在则明确 `RuntimeError` 拒绝加载并提示保留原库/启用新库（镜像 `core.py:103-110` 对无 scope 旧操作的先例），避免冻结余额被 NULL 行卡死且无法释放。
5. 同轮正常路径保持不变：B10→B21→B11→B12、B14 原操作回查、响应丢失后原编号恢复、订单只付一次、释放余额按银行事实。
6. 更新 `backend/app/services/mock_bank/README.md`：B10—B13/B20—B22 的轮次归属、错误码与拒绝语义；`bank_operation_scopes` 与对象归属的关系；02 启动拒绝 NULL 对象的边界。

## Acceptance criteria

- [ ] 网关在真实授权回调下，D2 对 D1 冻结/订单的 B13/B22 读取返回 `ACCESS_DENIED`；同轮读取仍成功；缺失对象仍 `RECORD_NOT_FOUND`。
- [ ] D2 用新编号核销/释放 D1 冻结：返回 `ACCESS_DENIED` 失败回执，无资金/冻结/订单/付款关联变化，不产生成功回执；**不接受 `OPERATION_CONFLICT`**；同轮正常核销/释放/付款保持通过。
- [ ] D2 创建订单带 D1 `order_id` 付款：拒绝 `ACCESS_DENIED`；同轮合法订单付款一次，重复执行只观察原操作。
- [ ] 银行库存在无轮次对象行时启动拒绝加载且不修改原库；正常库启动不受影响。
- [ ] 缺省无轮次的直接调用（既有测试/内部装配）行为不变，生产网关路径不再出现（测试可断言网关一定传轮次）。
- [ ] 只改 `backend/app/services/`；不触碰 security/agent_platform/storage/evals，不改公共契约字段，不新增业务规则。
- [ ] 修复后 `evals/mockbank/test_birthday_bank_eval.py` 的四项 strict xfail 预期 XPASS；须先备好 [v05-cross-bank-eval/02](../../v05-cross-bank-eval/issues/02-round-object-regression.md)，按 01→02→评测 02 相邻合入，或由中控记录接受红灯窗口；本票不修改评测期望。

## Verification

从 `backend/` 运行隔离临时库验证：

```powershell
$env:PYTHONPATH=(Get-Location).Path
python -m pytest -q app/services/ app/security/test_birthday_release.py --basetemp=<本票独立临时目录>
```

`app/security/test_birthday_release.py` 只读运行以确认释放收尾未被破坏，不改 security 文件、不纳入本票交付物；若确有跨目录问题交回安全/中控，不越界修复。真实 claim/执行器与银行局部装配验证可供评测票复用；不启动模型、HTTP 或页面。代码完成后两位独立子代理规范/规格审查、必须项闭合、单独 PR 回交，不自行合并；按 [spec 约束](../spec.md) 记录安全审阅（Erwin 代行或 Owner 判定不构成新安全规则），不写 Ringo 签核。
