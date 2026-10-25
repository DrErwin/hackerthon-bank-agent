# 02：银行服务与网关按可信轮次校验冻结/订单对象

Ticket ID: v05-bank-round-objects/02

Package: [v05-cross-linkage/packages/01-platform-bank：公共接缝与模拟银行](../../v05-cross-linkage/packages/01-platform-bank.md)

Spec: [本工作组规格](../spec.md)；责任判断与证据见[核查报告](../verification.md)。

Type: 开发

Core scenarios: 不适用（存储/服务基础设施票；对应验收见[包 06](../../v05-cross-linkage/packages/06-bank-eval.md)验收第 4 条与 [v05-cross-bank-eval/02](../../v05-cross-bank-eval/issues/02-round-object-regression.md)）。

Owner: Erwin（v0.5 统一承担）

Directory: `backend/app/services/`

Status: blocked — 等 01 合入及 `backend/app/services/` 目录窗口；未实施。

Blocked by: [v05-bank-round-objects/01：存储层对象轮次归属](01-object-round-storage.md)（实施依赖）。

Start when: 01 合入并取得 `backend/app/services/` 单目录窗口（生日线当前计划未列 services；若生日验证码票需要 services，先让其完成，见 [spec §协调与停止线](../spec.md)）。

## What to build

1. `MockBirthdayBank` 的写路径把本次可信上下文的 `demo_round_id` 传给存储原子提交（`freeze_funds`、`create_order`、`capture_frozen`、`release_frozen`）：
   - 冻结/订单创建写入归属轮次；
   - 核销/释放/订单付款关联由存储校验同轮次（缺省参数时必须显式传，不在服务层留绕过）。
2. 对象读取按可信上下文轮次校验：
   - `get_freeze` / `get_order` 增加可选 `demo_round_id` 服务参数；网关 `BankGateway.get_freeze` / `get_order` 传 `context.demo_round_id`；
   - 对象不存在 → 仍 `RECORD_NOT_FOUND`；对象存在但归属其他轮次 → `ACCESS_DENIED`；同轮次返回原视图。
   - 直接以旧参数调用（无轮次）只保留给既有测试装配，不得出现在生产/网关路径。
3. `_freeze_row` 与 `capture_frozen` / `release_frozen` 的冻结查找改按当前上下文轮次：返回 `ACCESS_DENIED` 并写失败回执（不移动资金）；`capture_frozen` 关联的订单也要同轮次校验；`create_order` 正常写入当前轮次。
4. 同轮正常路径保持不变：B10→B21→B11→B12、B14 原操作回查、响应丢失后原编号恢复、订单只付一次、释放余额按银行事实。
5. 更新 `backend/app/services/mock_bank/README.md`：B10—B13/B20—B22 的轮次归属与拒绝语义；`bank_operation_scopes` 与对象归属的关系。

## Acceptance criteria

- [ ] 网关在真实授权回调下，D2 对 D1 冻结/订单的 B13/B22 读取返回 `ACCESS_DENIED`；同轮读取仍成功。
- [ ] D2 用新编号核销/释放 D1 冻结：返回失败（`ACCESS_DENIED`），无资金/冻结/订单/付款关联变化，不产生成功回执；同轮正常核销/释放/付款保持通过。
- [ ] D2 创建订单带 D1 `order_id` 付款：拒绝；同轮合法订单付款一次，重复执行只观察原操作。
- [ ] 缺省无轮次的直接调用（既有测试/内部装配）行为不变，生产网关路径不再出现（测试可断言网关一定传轮次）。
- [ ] 只改 `backend/app/services/`；不触碰 security/agent_platform/storage/evals，不改公共契约字段，不新增业务规则。
- [ ] 修复后 `evals/mockbank/test_birthday_bank_eval.py` 的四项 strict xfail 预期出现 XPASS；由 [v05-cross-bank-eval/02](../../v05-cross-bank-eval/issues/02-round-object-regression.md) 立即转换为正式回归，本票不修改评测期望。

## Verification

从 `backend/` 运行隔离临时库验证：

```powershell
$env:PYTHONPATH=(Get-Location).Path
python -m pytest -q app/services/ app/security/test_birthday_release.py --basetemp=<本票独立临时目录>
```

`app/security/test_birthday_release.py` 只读运行以确认释放收尾未被破坏，不改 security 文件、不纳入本票交付物；若确有跨目录问题交回安全/中控，不越界修复。真实 claim/执行器与银行局部装配验证可供评测票复用；不启动模型、HTTP 或页面。代码完成后两位独立子代理规范/规格审查、必须项闭合、单独 PR 回交，不自行合并。
