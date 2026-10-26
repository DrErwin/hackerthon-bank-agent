# 01：存储层冻结/订单对象轮次归属

Ticket ID: v05-bank-round-objects/01

Package: [v05-cross-linkage/packages/01-platform-bank：公共接缝与模拟银行](../../v05-cross-linkage/packages/01-platform-bank.md)

Spec: [本工作组规格](../spec.md)；责任判断与证据见[核查报告](../verification.md)。

Type: 开发

Core scenarios: 不适用（存储/服务基础设施票；对应验收见[包 06](../../v05-cross-linkage/packages/06-bank-eval.md)验收第 4 条与 [v05-cross-bank-eval/02](../../v05-cross-bank-eval/issues/02-round-object-regression.md)）。

Owner: Erwin（v0.5 统一承担）

Directory: `backend/app/storage/`

Status: done — 2026-10-26 已 squash 合入 main `819bbfb`（PR #315）；双轴必须项已闭合；CI 计费未启动记 Blocked。专项四项 strict xfail 仍待 02/评测收口。

Blocked by: None（本票无实施前置票；Owner 决策与生日 storage 目录窗口是启动条件，见下，不是前置票）。
Source evidence: [PR #290：银行专项四项 strict xfail](https://github.com/DrErwin/hackerthon-bank-agent/pull/290)。

Start when: ①Owner 已确认补对象轮次列（见 [spec 背景](../spec.md)）；②生日系列 [v05-birthday-platform-dependencies/05：生日编辑候选检查点的一次封存](../../v05-birthday-platform-dependencies/issues/05-immutable-edit-checkpoint.md) 已合入并释放 `backend/app/storage/` 窗口（该线正在改 `storage/README.md`、`application.py`、`checkpoints.py`，本票也改 README，需 rebase/冲突处理）。

## What to build

1. 银行库 schema 升到 5：`freezes`、`orders` 增加对象轮次归属列 `demo_round_id TEXT`（可空）。`order_payments` 通过 `orders` 关联，不新增列。
2. `commit_operation` / `finalize_operation` 增加可选参数 `demo_round_id: str | None = None`：
   - 提供时，`FreezeOpening`、`OrderCreation` 落库写入该轮次；
   - 提供时，`_apply_object_effect` 对 `FreezeCapture`、`FreezeRelease`、订单付款关联校验目标对象轮次一致，不一致抛 `ValueError` 并随整个原子提交回滚（资金、账本、对象、回执全部不落）；
   - 不提供时保留现有行为（仅分阶段兼容/迁移遗留；**生产写入必须由服务票始终传轮次**，见 02）。
3. `get_freeze` / `get_order` 返回的行包含 `demo_round_id`（`SELECT *` 自然带出），供服务层“先取行、再比较轮次”；**不改变现有签名、不把轮次下推成存储过滤**（否则无法区分“不存在”与“他轮”）。
4. 旧库处理（沿用既有旧银行库先例，不做数据迁移）：
   - v4 且 `freezes`/`orders` 已有行：初始化时以明确 `RuntimeError` 拒绝加载，提示保留旧库、显式启用新银行库；不静默迁移/改写/清除。核查时只读抽查本机 `.mnemon` 两个演示库：`v03-local-demo` v3（13 ops / 13 scopes / 0 unscoped）、`v03-local-demo-browser-regression` v2（2 / 2 / 0），均无对象表；无 scope 检查不会拒绝，若加载会按 v2/v3 路径升到 v5 空对象表；未发现 v4 且含对象行的库；实施时按实际数据库检查。
   - v4 且对象表为空：`ALTER TABLE` 原地加列后升级，正常加载。
   - v3 及更早：按现有升级路径创建 v5 形状对象表（旧对象本就不存在）。
5. 更新 `backend/app/storage/README.md`：对象轮次归属、v4/v5 区别、旧库拒绝口径、过渡参数边界；与生日线 README 改动 rebase。

## Acceptance criteria

- [ ] 同用户、D1 创建冻结/订单（提交时带 D1），用 D2 轮次的核销/释放/订单付款关联提交被 `ValueError` 拒绝；余额、版本、冻结、订单、付款关联、账本与回执均保持不变（事务整体回滚）。
- [ ] 同轮（D1 对 D1）的冻结→核销→释放、订单创建→付款保持原有行为；原编号重放/异参冲突/重启持久化不变。
- [ ] 对象行带归属轮次，重启后仍可读取；`get_freeze`/`get_order` 返回该列且不按轮次过滤；过渡参数缺省时行为与当前一致（该兼容路径只允许测试/迁移遗留）。
- [ ] v4 有对象行库被明确拒绝且原表内容/`user_version` 不被修改（验证用表内容 + `user_version`，不用文件字节，避免 WAL 旁文件干扰）；v4 空对象行库可原地升级；v3 升级保持既有“重建空对象表”语义。
- [ ] 只改 `backend/app/storage/`；不触碰 services/security/evals；不迁移共享库；不在本票开测真实页面/模型。

## Verification

从 `backend/` 运行隔离临时库验证（`PYTHONPATH` 指向本 worktree，`--basetemp` 独立目录）：

```powershell
$env:PYTHONPATH=(Get-Location).Path
python -m pytest -q app/storage/ --basetemp=<本票独立临时目录>
```

补充针对本票新增/更新用例逐项记录命令、结果、JUnit/输出；不启动模型、HTTP 或页面。代码完成后两位独立子代理分别核对仓库规范与本票/规格，必须项修完再开单目录 PR 回交中控，不自行合并；按 [spec 约束](../spec.md) 记录安全审阅（Erwin 代行或 Owner 判定不构成新安全规则），不写 Ringo 签核。

## Delivery record

### 2026-10-26 实施

- 窗口与授权：PM 2026-10-26 14:39 告知生日线已完成、storage 窗口开放；2026-10-26 16:00 PM 在会话中明确确认「确认按推荐方案继续」（补对象轮次归属、继续 02/评测并开 PR）。main `2f5a58d`（生日九票与页面合入后）。
- 分支/worktree：`codex/v05-bank-round-objects-01`，独立 worktree `C:/Users/57652/.codex/worktrees/v05-bank-round/hackerthon-bank-agent`。
- 实施内容：银行库 `SCHEMA_VERSION=5`；`freezes`、`orders` 增 `demo_round_id`；`commit_operation`/`finalize_operation` 增可选 `demo_round_id`，对象创建写入、核销/释放/订单付款关联校验同轮次且随原子提交回滚；`get_freeze`/`get_order` 仍返回整行不按轮次过滤；v4 有对象行库初始化明确拒绝加载、v4 空对象表原地加列、v3 及更早创建 v5 形状表；更新 `backend/app/storage/README.md`。
- 本票验证（隔离临时目录，cwd=本 worktree `backend/`，`PYTHONPATH` 指向本 worktree）：
  - `python -m pytest -q app/storage/test_bank_cross_objects.py` → **16 passed**；
  - `python -m pytest -q app/storage` → **78 passed**；
  - 既有回归 `app/storage app/services/test_bank.py app/services/test_birthday_bank.py ../evals/mockbank/test_birthday_bank_eval.py` → **132 passed, 4 xfailed**（4 xfail 仍是本系列待修的裸银行跨轮对象探针，未改动）；
  - CI 既有银行评测 `../evals/mockbank/test_mockbank_eval.py` → **14 passed**；
  - 全后端：实现版（测试加齐前同一产品代码）**2113 passed, 13 skipped in 1148.17s**；测试加齐后的复跑在 30 分钟未出结果后主动终止（低 CPU、无进度），未作为证据，本票以 storage 目录测试与受影响回归为验收。
- 本机运维核对（只读）：`D:\hackerthon-bank-agent\.mnemon\v03-local-demo\mock_bank.sqlite3` 为 `user_version=3`、13 ops / 13 scopes / 0 unscoped、无 `freezes`/`orders` 表；`...v03-local-demo-browser-regression\mock_bank.sqlite3` 为 v2、2/2/0、无对象表。两库按 v2/v3 路径升到 v5 空对象表，不触发「v4 有对象行拒绝」；未发现 v4 且含对象行的本机库。本票未加载原库。
- 代码审查：规范轴与规格轴两位独立子代理已完成，代码语义无必须修复；测试/记录必须项已按意见修复（付款关联与回执快照、v4 保留账号、finalize 轮次、v4 单表拒绝参数化、本机库事实、Owner 确认记录）。
- 安全审阅：本票新增银行对象访问拒绝判定，按 AGENTS.md 属资金执行链路的安全相关改动；v0.5 阶段由 Erwin 代行审阅并如实记录为代行（不写 Ringo 签核）。PM 2026-10-26 16:10 指令「把这些都做了吧」批准继续推进合入；本条记录为本人代行推进，不补写 Ringo 签名。
- PR：[#315](https://github.com/DrErwin/hackerthon-bank-agent/pull/315)，最终提交 `1e3c0ad`（head `ddb21bb` 仅回填票面），**已 squash 合入 main `819bbfb`**（2026-10-26 16:11）。本票单独合入不关闭 services 的 fail-open，4 个 strict xfail 仍保留，按 spec 的 01→02→评测相邻合入顺序推进。
- CI：[Repository checks](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/40289698983/job/121461597432) 结论 failure，annotation 明确“job was not started because recent account payments have failed or your spending limit needs to be increased”；job 未运行、无测试执行证据，不记 CI 绿、非测试失败。仓库既有文档链接失败（`docs/versions/v0.5.0/completion.md` 相对路径少一级）已另行修复。
