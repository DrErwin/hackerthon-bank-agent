# 银行跨轮次旧对象边界：2026-10-26 只读核查与责任判断

状态：read-only completed — 只读核查最新 main、读取既有真实装配证据并在隔离目录复跑四项失败探针；未改产品代码、共享库或页面。责任判断供本系列后续实施与协调使用，不代替安全签核、页面 E2E 或 PM 接受。

基线：核查时点 `origin/main = 38b3b81`（2026-10-26 01:20；同日 00:39 在 `f2ab6d2` 之上新增生日系列领取文档；运行代码与 `5347dd7`/`f2ab6d2` 一致）。01:34 origin/main 前进到 `5b652e1`（仅 `.scratch/v05-cross-frontend/` 走查文档），01:50 起含本组本核查与票据提交；`backend/`、`evals/`、`docs/` 相对 38b3b81 无代码差异。核查在独立 worktree `C:/Users/57652/.codex/worktrees/v05-bank-round/hackerthon-bank-agent`，未写共享文档工作区，未启动模型、HTTP 服务或页面。

## 一、原始问题与两层证据

[包 06 银行专项验收](../v05-cross-linkage/packages/06-bank-eval.md)第 4 条要求“错误用户/账户/轮次、已释放或在途资金不能绕过原银行规则”。当前同时存在两类证据，必须分开：

1. **银行对象层缺口（未满足）**：[PR #290](https://github.com/DrErwin/hackerthon-bank-agent/pull/290) 保留的四项 strict xfail。同一银行库、同一用户，把可信上下文从 D1 换到 D2 后用新 `operation_id`，仍可：B13 读取 D1 冻结、B22 读取 D1 订单、B11 核销 D1 冻结并付掉 D1 订单、B12 释放 D1 冻结。探针只经显式测试授权回调，没有真实安全执行器，因此是**裸银行对象接口**证据，不是 HTTP/产品入口证据。
2. **产品路径门（已覆盖）**：[PR #294](https://github.com/DrErwin/hackerthon-bank-agent/pull/294) 的真实装配归因与 [PR #296](https://github.com/DrErwin/hackerthon-bank-agent/pull/296)（已合入 `620746a`）的订单来源门，证明旧会话/任务、旧释放授权、旧上下文、跨任务/上一轮订单在真实安全门和执行器下被拒绝。**不能把第 1 类探针直接写成产品可越权。**

本轮复跑确认第 1 类在最新 main 仍存在：

```powershell
cd backend
$env:PYTHONPATH=(Get-Location).Path
python -m pytest -q ../evals/mockbank/test_birthday_bank_eval.py -k old_round_objects --runxfail
# 2026-10-26 复核：4 failed, 37 deselected（四项均 OldRoundObjectAllowed）
python -m pytest -q ../evals/mockbank/test_birthday_round_attribution.py ../evals/mockbank/test_birthday_bank_eval.py app/agent_platform/test_birthday_order_scope.py app/agent_platform/test_birthday_runtime_wiring.py
# 2026-10-26 复核：53 passed, 4 xfailed（构成：归因 3 + 生日银行专项 41 = 37 通过 + 4 xfail + 订单来源门 8 + 生日真实装配 5 = 57 节点）
```

默认运行时四项为 `xfail(strict=True)`，不计通过；修复后出现 XPASS 会使专项失败并要求人工转换，不会被静默吞掉。节点收集（同日，`--collect-only`）：组合 57；`test_birthday_bank_eval.py` 单文件 41；`birthday-evidence.md` 记录的合跑命令（`../evals/mockbank app/services app/storage`）当前 175 节点（2026-10-25 报告为 153，随主线测试增补变化，按实际运行记录）。

## 二、责任判断：原约定要求银行独立拒绝到哪一层

必须分层，不能一概写成“原约定要求银行全链独立拒绝”：

1. **释放收尾链路有明文**：[公共契约 §9 M14](../../docs/contracts/公共契约-2026-09-23.md) 把“冻结 500、消费 199 后取消／安全终止只释放 301；在途付款未知不释放；恢复不重复释放、不恢复购买；**错误用户／冻结／轮次拒绝**”的验收责任列给 `cross + security + mockbank`；[安全与审计字段 §3.1](../../docs/contracts/安全与审计字段-2026-09-24.md) 明确限定释放“同用户、同任务、同轮次、同原账户”，并写明“**银行仍校验可信主体对原冻结的释放权限**”。因此 B12 释放链路的银行侧轮次拒绝是原约定明文。
2. **B13/B22 读取与 B11 核销是推导要求**：这两类原文只写归属，没有“轮次”二字——[银行接口字段 §2](../../docs/contracts/银行接口字段-2026-09-24.md)“本人账户及其操作记录才可查询；无权访问与无权判断其存在的资源统一拒绝”、§4 的 B13/B22 `ACCESS_DENIED`、§9.3“银行核对订单所属用户、商户、金额”、§11“授权范围内目标对象不存在 / 无权判断存在用 `ACCESS_DENIED`”，加上包 06 第 4 条。把“轮次”纳入这些对象的归属判断，是**对象归属层的防御纵深实现决策**，不是契约字面要求。
3. **规范的轮次切换是整体重置**：[公共契约 §7](../../docs/contracts/公共契约-2026-09-23.md) 与 [MockBank PRD](../../docs/prd/MockBank-PRD-2026-09-23.md) 的 B26 重置约定“清除全部动态信息（流水、预约单、冻结、订单），回到种子态”。四项探针模拟的“同库换 round 不重置”不是规范支持的切换方式，**不能据此指控产品可越权**；当前 F30/F31/B26 路由尚未实现（归因测试断言其缺失）。
4. **平台前门不是 §6.9**：§6.9 讲的是 `ResourceRef` 资源读取（`公共契约:591`）；平台对普通请求的轮次核验依据是 §6.4（“资源归属、会话有效性与当前轮次均由后端核验”，`:486`）、§6.5（“task_id 查询与 resume 均不得跨轮次”，`:522`）与 §6.3。平台门与银行归属是并行两层，不能互相替代，但不是“原约定把责任全给了银行”。
5. **实现层不一致**：`bank_operation_scopes` 自 v0.3 起按 `(user, round)` 绑定操作编号、B14 按轮次拒绝，这是银行服务的实现选择（契约只要求操作编号绑定身份）；它创建的冻结/订单对象没有轮次归属，是**同一银行服务内的实现不一致**，是补对象归属的一致性论据，不是契约规则。

结论：**释放收尾链路必须由银行按可信轮次拒绝（明文）；B11/B13/B22/B20/B21 对象层是否补轮次归属属于防御纵深决策**。原措辞“原约定要求银行在对象归属层独立拒绝”对 B12 成立、对 B11/B13/B22 是推导。因四项银行专项探针已按包 06 第 4 条冻结、B26 尚未实现，本组建议补对象归属而不是改评测去适配平台门（后者等于降低冻结要求）；**该防御纵深决策需 Owner 确认并记录，确认前不实施。**

## 三、最新 main 上游门已覆盖什么（具体证据）

| 层 | 已覆盖行为 | 证据（最新 main） |
|---|---|---|
| HTTP 会话/任务 | 旧轮次 cookie 在当前轮进程返回 401；D2 登录后旧任务 GET/resume 返回 404；B26 路由当前不存在 | `backend/app/api/service.py`（identity 按 `config.demo_round_id` 过滤、thread/link 按轮次、trusted 取当前轮次）；`evals/mockbank/test_birthday_round_attribution.py::test_asgi_old_session_and_task_are_not_current`（ASGI TestClient，非页面 E2E） |
| 安全执行器 | 真实 claim 放行前核对 `(user, round, task, action)`；旧上下文由 active-round 门先拒 `STALE_ROUND`，实际门另判 BLOCK/ACCESS_DENIED；旧释放授权按轮次读取为 ACCESS_DENIED | `backend/app/security/demo_policy.py`/`birthday_policy.py` 的 `_in_current_scope`；`birthday_release.py` 当前轮次与授权记录校验；`authorize_birthday_write`（仅 live ALLOW claim）；归因测试 `test_real_claim_gate_and_limited_release_reject_old_round` |
| 平台订单来源 | D2 当前任务对 D1 已知订单在确认前、执行前均 BLOCK/ACCESS_DENIED，零新确认、六类银行表不变；本任务同商品合法订单也不能替旧订单换权限，合法订单仍可付一次 | `backend/app/agent_platform/birthday_runtime.py::_order_source_allowed` + `authorize_tool`；`backend/app/agent_platform/test_birthday_order_scope.py`（含 `previous_round` 参数）；合入提交 `620746a`（PR #296） |
| 可达性 | B13/B22 不是模型工具、不注册 HTTP 路由；生日链路 freeze_id/order_id 来自任务快照/安全记录，不接受模型或用户直接给编号 | 归因测试末尾断言 `bank.get_freeze`/`bank.get_order` 未注册、无 freeze/order 路由；`birthday_runtime.py` 的 `_freeze_id`、`_capture_parameters` 取自任务存储与安全记录 |

业务含义：**普通用户当前没有“把旧轮次对象编号交给产品入口”的可达路径**，因此本轮不把四项探针写成产品/页面漏洞，也不追加平台或安全新规则。上游门是真实的，但它们各自只覆盖自己的产物路径；银行对象层的轮次拒绝是防御纵深决策（见 §二）。

## 四、修复范围（两项代码票 + 一项评测票）

银行对象事实缺轮次归属，使四项银行专项验收项无法在银行层收口：

- `backend/app/storage/mock_bank/repository.py`：`freezes`、`orders` 表无 `demo_round_id`；`FreezeOpening`/`OrderCreation` 不携带轮次；`_require_freeze`、`get_freeze`、`get_order` 只按用户。
- `backend/app/storage/mock_bank/repository.py::_apply_object_effect`：核销/释放/订单付款关联只校验同用户，不校验同轮次。
- `backend/app/services/mock_bank/birthday.py`：`_freeze_row`、`capture_frozen`、`release_frozen`、`create_order`、`get_freeze`、`get_order` 只使用 `user_id`。
- `backend/app/services/bank_gateway/gateway.py`：B13/B22 读取只传 `context.user_id`，未传可信上下文轮次。

修复拆成：

1. [v05-bank-round-objects/01：存储层对象轮次归属](issues/01-object-round-storage.md)，目录 `backend/app/storage/`。
2. [v05-bank-round-objects/02：银行服务与网关按轮次校验对象](issues/02-object-round-services.md)，目录 `backend/app/services/`，依赖 01。
3. [v05-cross-bank-eval/02：跨轮次旧对象边界回归收口](../v05-cross-bank-eval/issues/02-round-object-regression.md)，目录 `evals/mockbank/`，依赖 02；四项 strict xfail 转正式回归。

## 五、语义、错误码与数据边界（实施前定死）

- **读取实现**：服务先按 user 取整行（`store.get_freeze(user_id, ...)`/`get_order` 返回含 `demo_round_id` 的行），再比较当前可信轮次；**不得把轮次下推成存储过滤查询**，否则区分不了“不存在”与“他轮”。
- **错误码**：四项跨轮拒绝统一用 `ACCESS_DENIED`，依据银行接口字段 §8“ACCESS_DENIED 无权访问目标，不透露目标是否存在或属于谁”与 §2“无权访问与无权判断其存在的资源统一拒绝”；`RECORD_NOT_FOUND` 只表示授权范围内确不存在（§11），不用于“同用户他轮对象”；**禁止用 `OPERATION_CONFLICT` 表示跨轮拒绝**，否则会把所有权拒绝伪装成同编号参数冲突（现有 `gateway.py` 会把存储 `ValueError` 映射成该码，实施时须保证由服务预检返回明确拒绝）。
- **NULL/过渡态**：存储票的可选轮次参数只服务分阶段兼容；生产写入必须始终带轮次。02 在 `MockBankService` 初始化时检查冻结/订单对象是否有无轮次行，有则拒绝加载并保留原库（镜像 `core.py:103-110` 对无 scope 旧操作的先例），避免“冻结余额被 NULL 行卡死且无法释放”。两票之间不得作为可运行演示状态。
- **旧库**：不做共享库迁移。已有 v4 演示库若已有冻结/订单行，明确拒绝加载、保留原库、显式启用新库；空对象表的 v4 库原地加列；v3 及更早仍按现有升级路径重建对象表。核查时抽查本机 `.mnemon` 两个演示库为 v2/v3、均已被 `core.py` 无 scope 检查拒绝，未发现 v4 且含对象行的库；实施前仍须按实际检查，不能假设。写入文件/表的“不修改原库”验证应以表内容 + `user_version` 为准，不用文件字节（WAL 旁文件会影响哈希）。
- **XPASS 时序**：02 合入后四项 strict xfail 变 XPASS，专项在 main 上会红到评测票合入。实施须先备好评测票分支与证据，按“01 → 02 → 评测 02”相邻合入，或由中控明确记录并接受红灯窗口及对 `evals 57+4` 冒烟口径的临时影响；不能只写“立即转换”。
- **安全审阅**：两票新增 `ACCESS_DENIED` 判定属银行对象访问权限（资金执行链路）。按根 `AGENTS.md`，安全规则由 Erwin 在 v0.5 阶段代行审阅并如实记录为代行（不写 Ringo 签核）；若 Owner 判定“补对象归属不构成新安全规则”，须在票面留痕。
- 同轮正常路径保持：B10→B21→B11→B12、原操作回查、响应未知沿原编号恢复、合法订单只付一次、缺失对象仍为 `RECORD_NOT_FOUND`。

## 六、验证与停止线

- 每票只做本目录局部验证（隔离临时 SQLite），按票记录实际命令、结果和产物；代码票另做两位独立子代理的规范/规格审查、必修项修复、单独 PR 回交，不自行合并。
- 评测收口后分两个口径记录：①`evals/mockbank/test_birthday_bank_eval.py` 单文件 41 项（原 37 通过 + 4 项转正）全部通过、0 xfailed；②`birthday-evidence.md` 记录的合跑命令按实施后实际节点全绿、0 failed/0 xfailed（2026-10-25 为 153 节点、2026-10-26 收集 175 节点，按实际记录不写死数量）。四项都要断言具体拒绝码（读取 `ACCESS_DENIED`、写入 `ACCESS_DENIED`；不接受 `OPERATION_CONFLICT`），并保留合法订单/同轮对照与历史失败证据。
- **不在本系列自动运行**：真实页面/模型/银行全链 E2E、B26 正式重置、整体银行专项接受、安全专项、Ringo 真人签核、PM 最终体验接受。本轮未启动模型或 HTTP 服务。
- 原四项探针、历史和 JUnit 保留；修复后新增证据另存，不改写历史失败记录。

## 七、归属、跨包与目录协调

- **跨包归属**：两票挂在包 01（唯一覆盖 storage/services 的包），但收口的是包 06 第 4 条；须在包 01 验收/回交中登记该跨包要求，评测票在包 06 收口。
- **归因测试所有权**：评测票要改的 `test_birthday_round_attribution.py` 属 [v05-cross-bank-round-attribution/01](../v05-cross-bank-round-attribution/issues/01-round-boundary-attribution.md)（同 Owner、同目录、不同工作组）的交付物。评测票须在其更新清单加入该归因组票与 `evals/mockbank/round-attribution.md` 的当前状态修正（296=`620746a`、294=`ad401ac` 已合入；历史失败段保持不动），并回写该组记录。
- **与生日线**：生日线正在实时使用 `backend/app/storage/`（2026-10-26 01:40 分支 `codex/v05-birthday-immutable-checkpoint` 提交 `3e38506 feat(storage): 候选检查点一次封存与应用库 v7`、`c886660`，改动含 `storage/README.md`、`application.py`、`checkpoints.py`），本组 01 也要改 `storage/README.md`，须等其合入并做 rebase/冲突处理。生日系列 §4 第 4 条写明若验证码原子撤离需要 services 会新增单目录票，因此本组 02 的 services 窗口按“生日需要的目录先完成”排队，而不是假设其永不使用 services。评测票在 `evals/mockbank/`，不与人共用，但仍等 02 合入顺序。
- **B26 后置**：对象轮次列在 B26 正式重置落地后可能部分冗余；保留/移除由 B26 落地后决定，本组不现在处理。
