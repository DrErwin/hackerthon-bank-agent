# 01：存储层冻结/订单对象轮次归属

Ticket ID: v05-bank-round-objects/01

Package: [v05-cross-linkage/packages/01-platform-bank：公共接缝与模拟银行](../../v05-cross-linkage/packages/01-platform-bank.md)

Spec: [本工作组规格](../spec.md)；责任判断与证据见[核查报告](../verification.md)。

Type: 开发

Core scenarios: 不适用（存储/服务基础设施票；对应验收见[包 06](../../v05-cross-linkage/packages/06-bank-eval.md)验收第 4 条与 [v05-cross-bank-eval/02](../../v05-cross-bank-eval/issues/02-round-object-regression.md)）。

Owner: Erwin（v0.5 统一承担）

Directory: `backend/app/storage/`

Status: blocked — 等生日线释放 `backend/app/storage/` 目录窗口，未实施。

Blocked by: None（本票无实施前置票）。
Source evidence: [PR #290：银行专项四项 strict xfail](https://github.com/DrErwin/hackerthon-bank-agent/pull/290)。

Start when: 生日系列完成 [v05-birthday-platform-dependencies/05：生日编辑候选检查点的一次封存](../../v05-birthday-platform-dependencies/issues/05-immutable-edit-checkpoint.md) 并释放 storage 单目录窗口；本票不依赖生日行为，仅共用目录需排队（见 [spec §协调与停止线](../spec.md)）。

## What to build

1. 银行库 schema 升到 5：`freezes`、`orders` 增加对象轮次归属列 `demo_round_id TEXT`（可空；仅用于兼容未接入的过渡写入）。`order_payments` 通过 `orders` 关联，不新增列。
2. `commit_operation` / `finalize_operation` 增加可选参数 `demo_round_id: str | None = None`：
   - 提供时，`FreezeOpening` 落库写入该轮次；`OrderCreation` 也一样；
   - 提供时，`_apply_object_effect` 对 `FreezeCapture`、`FreezeRelease`、订单付款关联校验目标对象轮次一致，不一致抛 `ValueError` 并随整个原子提交回滚（资金、账本、对象、回执全部不落）；
   - 不提供时保留现有行为（过渡兼容），但过渡期写入的行没有归属，按旧对象处理。
3. `get_freeze` / `get_order` 返回的行包含 `demo_round_id`（`SELECT *` 自然带出），供服务层判定；不改变现有签名。
4. 旧库处理（沿用既有旧银行库先例，不做数据迁移）：
   - v4 且 `freezes`/`orders` 已有行：初始化时以明确 `RuntimeError` 拒绝加载，提示保留旧库、显式启用新银行库；不静默迁移/改写/清除。
   - v4 且对象表为空：`ALTER TABLE` 原地加列后升级，正常加载。
   - v3 及更早：按现有升级路径创建 v5 形状对象表（旧对象本就不存在）。
5. 更新 `backend/app/storage/README.md`：对象轮次归属、旧库拒绝口径、过渡参数的边界。

## Acceptance criteria

- [ ] 同用户、D1 创建冻结/订单（提交时带 D1），用 D2 轮次的核销/释放/订单付款关联提交被 `ValueError` 拒绝；余额、版本、冻结、订单、付款关联、账本与回执均保持不变（事务整体回滚）。
- [ ] 同轮（D1 对 D1）的冻结→核销→释放、订单创建→付款保持原有行为；原编号重放/异参冲突/重启持久化不变。
- [ ] 对象行带归属轮次，重启后仍可读取；过渡参数缺省时行为与当前一致，写入行的归属为空。
- [ ] v4 有对象行库被明确拒绝且原文件不被修改；v4 空对象行库可原地升级；v3 升级保持既有“重建空对象表”语义。
- [ ] 只改 `backend/app/storage/`；不触碰 services/security/evals；不迁移共享库。

## Verification

从 `backend/` 运行隔离临时库验证（`PYTHONPATH` 指向本 worktree，`--basetemp` 独立目录）：

```powershell
$env:PYTHONPATH=(Get-Location).Path
python -m pytest -q app/storage/ --basetemp=<本票独立临时目录>
```

补充针对本票新增/更新用例逐项记录命令、结果、JUnit/输出；不启动模型、HTTP 或页面。代码完成后两位独立子代理分别核对仓库规范与本票/规格，必须项修完再开单目录 PR 回交中控，不自行合并。
