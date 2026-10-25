# 银行跨轮次旧对象边界：2026-10-26 只读核查与责任判断

状态：read-only completed — 只读核查最新 main、读取既有真实装配证据并在隔离目录复跑四项失败探针；未改产品代码、共享库或页面。责任判断供本系列后续实施与协调使用，不代替安全签核、页面 E2E 或 PM 接受。

基线：核查时点 `origin/main = 38b3b81`（2026-10-26 01:20，同日 00:39 在 `f2ab6d2` 之上新增生日系列领取文档；运行代码与 `5347dd7`/`f2ab6d2` 一致）。截至 2026-10-26 01:34，origin/main 已前进到 `5b652e1`（仅在 `.scratch/v05-cross-frontend/` 增加生日页面走查文档，无运行代码差异）。核查在独立 worktree `C:/Users/57652/.codex/worktrees/v05-bank-round/hackerthon-bank-agent`，未写共享文档工作区，未启动模型、HTTP 服务或页面。

## 一、原始问题与两层证据

[包 06 银行专项验收](../v05-cross-linkage/packages/06-bank-eval.md)的验收第 4 条要求“错误用户/账户/轮次、已释放或在途资金不能绕过原银行规则”。当前同时存在两类证据，必须分开：

1. **银行对象层缺口（未满足）**：[PR #290](https://github.com/DrErwin/hackerthon-bank-agent/pull/290) 保留的四项 strict xfail。同一银行库、同一用户，把可信上下文从 D1 换到 D2 后用新 `operation_id`，仍可：B13 读取 D1 冻结、B22 读取 D1 订单、B11 核销 D1 冻结并付掉 D1 订单、B12 释放 D1 冻结。探针只经显式测试授权回调，没有真实安全执行器，因此是**裸银行对象接口**证据，不是 HTTP/产品入口证据。
2. **产品路径门（已覆盖）**：[PR #294](https://github.com/DrErwin/hackerthon-bank-agent/pull/294) 的真实装配归因与 [PR #296](https://github.com/DrErwin/hackerthon-bank-agent/pull/296)（已合入 `620746a`）的订单来源门，证明旧会话/任务、旧释放授权、旧上下文、跨任务/上一轮订单在真实安全门和执行器下被拒绝。**不能把第 1 类探针直接写成产品可越权。**

本轮复跑确认第 1 类在最新 main 仍存在：

```powershell
cd backend
$env:PYTHONPATH=(Get-Location).Path
python -m pytest -q ../evals/mockbank/test_birthday_bank_eval.py -k old_round_objects --runxfail
# 2026-10-26 复核：4 failed, 37 deselected in 0.60s（四项均 OldRoundObjectAllowed）
```

默认运行（不带 `--runxfail`）时这四项为 `xfail(strict=True)`，不计通过；修复后出现 XPASS 会使专项失败并要求人工转换，不会被静默吞掉。

同点复跑组合基线（与 `evals/mockbank/round-attribution.md` 记录口径一致，隔离临时目录）：

```powershell
cd backend
$env:PYTHONPATH=(Get-Location).Path
python -m pytest -q ../evals/mockbank/test_birthday_round_attribution.py ../evals/mockbank/test_birthday_bank_eval.py app/agent_platform/test_birthday_order_scope.py app/agent_platform/test_birthday_runtime_wiring.py
# 2026-10-26 复核：53 passed, 4 xfailed in 83.82s
# 构成：归因 3 + 生日银行专项 41（37 通过 + 4 xfail）+ 订单来源门 8 + 生日真实装配 5 = 57 节点
```

节点收集（同日，`--collect-only`）：组合 57 = 3+41+8+5；`test_birthday_bank_eval.py` 单文件 41；`birthday-evidence.md` 记录的合跑命令（`../evals/mockbank app/services app/storage`）当前收集为 175 节点（2026-10-25 报告记录为 153 节点，随主线测试增补变化，按实际运行记录，不写死节点数）。

## 二、责任判断：原约定要求银行独立拒绝到哪一层

结论：**原约定要求银行在“对象归属”层独立拒绝错误轮次的冻结/订单读取与实际使用；平台与安全门是另一层资源授权，不能替代银行对象归属校验。**

依据：

- [银行接口字段 §2](../../docs/contracts/银行接口字段-2026-09-24.md)：“查询权限——本人账户及其操作记录才可查询；无权访问与无权判断其存在的资源统一拒绝”。B13/B22 的拒绝码列明 `ACCESS_DENIED`；B11/B12/B21 为写能力（B20 商品目录、B22 订单为只读）。冻结与订单是银行自有事实，只有银行能判定其归属。
- [安全与审计字段 §2](../../docs/contracts/安全与审计字段-2026-09-24.md)：安全裁决“先核验可信身份与资源归属”，执行前核对“实际用户、会话、轮次、任务、操作编号、动作版本及参数一致”；§3.1 限定释放只覆盖“同用户、同任务、同轮次、同原账户”，并明确“银行仍校验可信主体对原冻结的释放权限”。验收 S02/S07 把“轮次不匹配不放行”和“旧轮次不得执行”列为可检查项。
- [公共契约 §6.9](../../docs/contracts/公共契约-2026-09-23.md)：平台负责资源读取的会话/轮次/用途核验，“旧轮次普通资源不可继续办理业务”。这是平台侧的**前门**责任，与银行侧归属校验并行，不是替代关系。
- 现有实现自身已有的轮次概念：银行自 v0.3 起用 `bank_operation_scopes` 按 `(user_id, demo_round_id)` 绑定操作编号与轮次（`backend/app/services/mock_bank/core.py` 建表/校验，`birthday.py::_reserve_scope`），B14 回查已按轮次拒绝（`core.py::get_operation`）。操作编号已按轮次归属，而它创建的冻结/订单对象没有归属，属同一银行规则内的不一致，不是新增业务政策。
- 边界：本项只补“对象属于当前可信轮次”的归属判断，不新增限额/风控/是否该买等业务规则，不改公共契约字段；错误语义沿用银行既有 `ACCESS_DENIED`（对象存在但不在当前可信范围）/`RECORD_NOT_FOUND`（不存在），不复制银行规则到业务模块。

需要同时说明的相反证据：公共契约 §7 的 B26 重置约定“银行恢复种子态”，即**正式轮次切换应通过整体重置让旧对象消失**；当前 F30/F31/B26 路由尚未实现，“同库改配置重启不算重置”（见 `evals/mockbank/test_birthday_round_attribution.py` 断言 B26 路由缺失）。因此：

- 四项探针模拟的“同库换 round 不重置”不是规范支持的轮次切换方式，**不能据此指控产品可越权**；
- 但包 06 的验收对象是银行专项本身，规范轮次切换未实现并不能把“银行对象按用户跨轮可用”变成满足项；银行层补归属是防御纵深，也让四项缺口可独立收口，而不依赖尚未实现的 B26。

## 三、最新 main 上游门已覆盖什么（具体证据）

| 层 | 已覆盖行为 | 证据（最新 main） |
|---|---|---|
| HTTP 会话/任务 | 旧轮次 cookie 在当前轮进程返回 401；D2 登录后旧任务 GET/resume 返回 404；B26 路由当前不存在 | `backend/app/api/service.py`（identity 按 `config.demo_round_id` 过滤、thread/link 按轮次、trusted 取当前轮次）；`evals/mockbank/test_birthday_round_attribution.py::test_asgi_old_session_and_task_are_not_current`（ASGI TestClient，非页面 E2E） |
| 安全执行器 | 真实 claim 放行前核对 `(user, round, task, action)`；旧上下文由 active-round 门先拒 `STALE_ROUND`，实际门另判 BLOCK/ACCESS_DENIED；旧释放授权按轮次读取为 ACCESS_DENIED | `backend/app/security/demo_policy.py`/`birthday_policy.py` 的 `_in_current_scope`；`birthday_release.py` 当前轮次与授权记录校验；`authorize_birthday_write`（仅 live ALLOW claim）；归因测试 `test_real_claim_gate_and_limited_release_reject_old_round` |
| 平台订单来源 | D2 当前任务对 D1 已知订单在确认前、执行前均 BLOCK/ACCESS_DENIED，零新确认、六类银行表不变；本任务同商品合法订单也不能替旧订单换权限，合法订单仍可付一次 | `backend/app/agent_platform/birthday_runtime.py::_order_source_allowed` + `authorize_tool`；`backend/app/agent_platform/test_birthday_order_scope.py`（含 `previous_round` 参数）；合入提交 `620746a`（PR #296） |
| 可达性 | B13/B22 不是模型工具、不注册 HTTP 路由；生日链路 freeze_id/order_id 来自任务快照/安全记录，不接受模型或用户直接给编号 | 归因测试末尾断言 `bank.get_freeze`/`bank.get_order` 未注册、无 freeze/order 路由；`birthday_runtime.py` 的 `_freeze_id`、`_capture_parameters` 取自任务存储与安全记录 |

业务含义：**普通用户当前没有“把旧轮次对象编号交给产品入口”的可达路径**，因此本轮不把四项探针写成产品/页面漏洞，也不追加平台或安全新规则。上游门是真实的，但它们各自只覆盖自己的产物路径，不能替代银行对社会事实（冻结/订单归属）的最终判定。

## 四、仍缺的既定约束（本轮形成的修复范围）

银行对象事实缺轮次归属，导致四项银行专项验收项未满足：

- `backend/app/storage/mock_bank/repository.py`：`freezes`、`orders` 表无 `demo_round_id`；`FreezeOpening`/`OrderCreation` 不携带轮次；`_require_freeze`、`get_freeze`、`get_order` 只按用户。
- `backend/app/storage/mock_bank/repository.py::_apply_object_effect`：核销/释放/订单付款关联只校验同用户，不校验同轮次。
- `backend/app/services/mock_bank/birthday.py`：`_freeze_row`、`capture_frozen`、`release_frozen`、`create_order`、`get_freeze`、`get_order` 只使用 `user_id`。
- `backend/app/services/bank_gateway/gateway.py`：B13/B22 读取只传 `context.user_id`，未传可信上下文轮次。

最小修复拆成两票（一票一目录）：

1. [v05-bank-round-objects/01：存储层对象轮次归属](issues/01-object-round-storage.md)，目录 `backend/app/storage/`。
2. [v05-bank-round-objects/02：银行服务与网关按轮次校验对象](issues/02-object-round-services.md)，目录 `backend/app/services/`，依赖 01。
3. 评测收口由 [v05-cross-bank-eval/02](../v05-cross-bank-eval/issues/02-round-object-regression.md) 承接，目录 `evals/mockbank/`，依赖 02；真实约束满足后才把四项 strict xfail 改成正式回归，不删测试、不降期望。

## 五、兼容与数据边界

- **不做共享库迁移**：冻结/订单对象归属是新列；对已有 v4 演示银行库，若其中已有冻结/订单行（无法证明其轮次），按仓库既有口径**明确拒绝加载并要求保留旧库、显式启用新银行库**（见 `backend/app/services/mock_bank/README.md` 对旧操作库的先例），不静默迁移、不改写、不清除。空对象表的 v4 库可原地加列；v3 及更早仍按现有升级路径重建对象表。该操作影响需在实施前向 PM 说明并由 PM 决定是否接受。
- 实施期间开发/验证只用全新绝对隔离数据目录，不碰共享 `.mnemon/` 演示库或原 E2E 库。
- 中间态兼容：存储票先提供可选归属参数并直接覆盖新行为测试；服务票再把网关/银行所有调用点接入并打开校验。两票之间不能被当作可运行演示状态。
- 错误语义：不存在的对象仍是 `RECORD_NOT_FOUND`；存在但属于其他轮次的对象，读取与写入返回 `ACCESS_DENIED`（或按 B13/B22 允许的拒绝码），不得移动资金、不得留下成功回执。
- 同轮正常路径必须保持：B10→B21→B11→B12、原操作回查、响应未知沿原编号恢复、合法订单只付一次。

## 六、验证与停止线

- 每票只做本目录局部验证（隔离临时 SQLite），按票记录实际命令、结果和产物；代码票另做两位独立子代理的规范/规格审查，必须项修完后单独 PR 回交，不自行合并。
- 评测收口后分两个口径记录：①`evals/mockbank/test_birthday_bank_eval.py` 单文件 41 项（原 37 通过 + 4 项转正）全部通过、0 xfailed；②`birthday-evidence.md` 记录的合跑命令按实施后实际节点全绿、0 failed/0 xfailed（2026-10-25 为 153 节点、2026-10-26 收集 175 节点；数量变化按实际记录，不凑数）。同一轮保留合法订单/同轮对照与历史失败证据。
- **不在本系列自动运行**：真实页面/模型/银行全链 E2E、B26 正式重置、整体银行专项接受、安全专项、Ringo 真人签核、PM 最终体验接受。本轮未启动模型或 HTTP 服务。
- 原四项探针、历史和 JUnit 保留；修复后新增证据另存，不改写历史失败记录。

## 七、目录协调（与生日线）

生日系列与本系列共用 `backend/app/storage/`、`backend/app/services/`（以及可能的 `backend/app/security/`、`backend/app/agent_platform/`）。2026-10-26 01:20 核查：生日线已在独立 worktree `v05-birthday-t01` 修改 `backend/app/agent_platform/birthday_runtime.py`（数量/稳定执行项，本地提交 `189c651 feat(agent_platform): 生日真实数量与稳定执行项装配`），按生日交接下一步是存储 05（不可变封存）、安全 02。

因此本系列的目录窗口：

1. 等待生日线完成其 `backend/app/storage/` 票（05）后，申请 storage 单目录窗口实施 01；
2. 01 合入后再申请 `backend/app/services/` 窗口实施 02（生日线当前计划未列 services，但验证码原子撤离若需要必须另排）；
3. 最后实施评测票（`evals/mockbank/` 不与其他线共用，仍需等 02 合入以避免 strict xfail XPASS 干扰专项）。
