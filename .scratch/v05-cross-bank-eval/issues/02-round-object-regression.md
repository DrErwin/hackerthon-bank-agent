# 02：跨轮次旧对象边界回归收口

Ticket ID: v05-cross-bank-eval/02

Package: [v05-cross-linkage/packages/06-bank-eval：银行专项验收](../../v05-cross-linkage/packages/06-bank-eval.md)

Spec: [本工作组规格](../spec.md)；责任判断与证据见[v05-bank-round-objects 核查报告](../../v05-bank-round-objects/verification.md)。

Type: 评测

Core scenarios: XL-B01 的跨轮次分支；定义见[共享规格 §5](../../v05-cross-linkage/spec.md)。

Owner: Erwin

Directory: `evals/mockbank/`

Status: done — 2026-10-26 已 squash 合入 main `5b4b99d`（PR #317）；四项 strict xfail 转正、混合订单轮次用例与证据已交付；CI 计费未启动记 Blocked。

Blocked by: [v05-bank-round-objects/02：银行服务与网关按可信轮次校验冻结/订单对象](../../v05-bank-round-objects/issues/02-object-round-services.md)（01 是 02 的传递前置，见 [01](../../v05-bank-round-objects/issues/01-object-round-storage.md)；另需 Owner 确认补对象归属，见 [spec 背景](../../v05-bank-round-objects/spec.md)）。

Source: [PR #290](https://github.com/DrErwin/hackerthon-bank-agent/pull/290) 四项 strict xfail；[PR #294](https://github.com/DrErwin/hackerthon-bank-agent/pull/294) 归因；[PR #296](https://github.com/DrErwin/hackerthon-bank-agent/pull/296) 平台订单来源门（已合入 `620746a`）。

## What to build

真实约束满足后，把银行专项的四项已知缺口转成正式回归，并让归因测试不再依赖“D2 可读 D1 对象”这一将被关闭的行为：

1. `test_birthday_bank_eval.py::test_old_round_objects_with_new_operation_are_denied`：
   - 去掉 `xfail(strict=True)` 与 `OldRoundObjectAllowed` 例外类型；
   - 四项**都断言具体拒绝码**：D2 对 D1 冻结/订单的 B13/B22 读取为 `ACCESS_DENIED`；D2 新编号核销/释放 D1 冻结为 `ACCESS_DENIED` 失败回执；**明确不接受 `OPERATION_CONFLICT`**（避免把所有权拒绝伪装成同编号参数冲突，见 [核查报告 §五](../../v05-bank-round-objects/verification.md)）；
   - 断言六类银行事实（accounts/freezes/orders/order_payments/ledger_entries/bank_operations）除允许的失败回执外不变，无资金移动；
   - 增加同轮次正常对照：D1 读取/核销/释放仍成功，合法订单只付一次；缺失对象仍 `RECORD_NOT_FOUND`。
   - 增加 `test_current_round_freeze_cannot_pay_another_round_order`：D2 本轮冻结 + D1 `order_id` 的核销必须 `ACCESS_DENIED`、订单仍 unpaid、账户/冻结/订单付款/账本不变；同轮 D2 订单 + D2 冻结仍付款一次。原四项的 capture 前置是 D1 freeze + D1 order，只覆盖冻结轮次，本用例补订单轮次校验。
2. `test_birthday_round_attribution.py`：
   - 该文件是 [v05-cross-bank-round-attribution/01](../../v05-cross-bank-round-attribution/issues/01-round-boundary-attribution.md) 的交付物（同 Owner/目录、不同工作组）。本票修改时须在该归因组票追加交接记录，并把 `evals/mockbank/round-attribution.md` 的“当前状态”更正为：PR #296=`620746a`、PR #294=`ad401ac` 已合入 main；**历史失败/未合入段落原样保留，不改写历史**；在该文第 3 行旧状态处加“已被本报告当前状态取代（superseded）”注记，供落地前引用；
   - 该文件此前用 D2 网关读取旧订单/旧冻结来核对“旧订单仍 unpaid、旧冻结仍 500”（`current.gateway.get_order(who=D2, old_order_id)` 等）；对象轮次校验打开后这些读取会变为拒绝。改为**直接银行库事实**（`bank_state` 的 orders/freezes 行）观察，保留“旧订单仍 unpaid、旧冻结仍 500”的事实断言；不删除任何反例、不把历史失败改成通过；
   - 已核对不受本次修复影响、无需修改：`test_fresh_seed_repeats_results_and_old_resources_are_absent`（每轮新建库，旧对象本就不存在 → 仍 `RECORD_NOT_FOUND`）、`test_operation_scope_isolation`（操作编号 scope 已按轮次拒绝）、`test_wrong_owner_and_exhausted_freeze_cannot_move_money`（跨用户仍 `RECORD_NOT_FOUND`）、security 的 restart/release 用例（直接 `birthday.get_freeze("U1", …)` 走兼容白名单）。
3. 证据与文档：
   - 重新运行 `evals/mockbank/birthday-evidence.md` 记录的专项命令；分两个口径：①`test_birthday_bank_eval.py` 单文件 42 项（原 37 项 + 4 项转正 + 1 混合轮次订单）全部通过、0 xfailed；②合跑命令按实际节点全绿、0 failed/0 xfailed（2026-10-26 实际 217 passed；不写死历史节点数、不凑数）；
   - 新 JUnit 保存到独立证据目录（`evals/mockbank/evidence/2026-10-26/`，目录由本票创建），历史 strict xfail 与归因失败 XML 原样保留；
   - 更新 `birthday-evidence.md`、`round-attribution.md`、`v05-cross-bank-eval/01`、`round-boundary-gap.md`、归因组票与本票状态；报告明确区分：银行对象层回归通过 ≠ 页面/HTTP/模型 E2E 通过 ≠ B26 整体重置 ≠ 安全专项/真人签核/PM 接受。
4. **合入时序**：02 合入后四项 strict xfail 会 XPASS、专项在 main 变红；实际窗口还包含归因测试 1 项失败（D2 网关读旧对象），即 `evals/mockbank` 5 failed / 53 passed。02 已于 `b63ec1b` 合入，本票在其后 rebase 到 main 并完成转正；合入后窗口归零。本票以 01→02→评测相邻合入交付。

## Acceptance criteria

- [x] 四项原 strict xfail 转为普通断言并实际通过；每一项都断言具体拒绝码（读取/写入 `ACCESS_DENIED`，`OPERATION_CONFLICT` 不被接受）；`--runxfail` 不再出现 `OldRoundObjectAllowed`；没有以放宽断言/删除用例换绿。
- [x] 同轮正常冻结→下单→核销→释放、原编号回查、响应丢失恢复、合法订单只付一次、缺失对象 `RECORD_NOT_FOUND` 继续通过。
- [x] 专项命令实际结果：单文件 42 项全部通过、0 xfailed；合跑命令 217 passed、0 failed/0 xfailed。
- [x] 归因测试仍在最新 main 上通过，产品边界/ASGI/内部端口/历史失败证据与结论保持；`round-attribution.md` 的 296/294 合并状态已更正、历史段原样；归因组票有交接记录。
- [x] 只改 `evals/mockbank/` 与银行评测组/归因组文档（含 `.scratch/v05-bank-round-objects/spec.md` 状态行）；不改产品代码，不改共享项目跟踪/版本 completion。

## Delivery record

### 2026-10-26 实施

- 分支/worktree：`codex/v05-bank-round-eval-02`，独立 worktree `C:/Users/57652/.codex/worktrees/v05-bank-round-eval/hackerthon-bank-agent`；已 rebase 到 02/services 合入后的 main `b63ec1b`。
- 改动：`test_birthday_bank_eval.py` 去掉 strict xfail/自定义例外，四项断言 `ACCESS_DENIED`（写入不得是 `OPERATION_CONFLICT`）并保留六表对照；新增混合轮次订单用例（D2 冻结 + D1 订单拒绝，同轮对照）；`test_birthday_round_attribution.py` 改用银行库事实观察旧订单/旧冻结，不再用 D2 网关读；更新 `birthday-evidence.md`、`round-attribution.md`（含 296/294 合并状态、superseded/历史标记），回写归因组票；更新 `.scratch/v05-bank-round-objects/spec.md` 状态；新增 JUnit `evidence/2026-10-26/bank-round-objects.xml`。
- 实跑（隔离临时目录，cwd 本 worktree `backend/`）：
  - `../evals/mockbank/test_birthday_bank_eval.py` → **42 passed**；
  - `../evals/mockbank/test_birthday_round_attribution.py` → **3 passed**；
  - `../evals/mockbank app/services app/storage` → **217 passed, 0 xfailed in 39.27s**（JUnit tests=217、0 fail/error/skip）；
  - `../evals/mockbank/test_mockbank_eval.py` → **14 passed**；
  - `app/agent_platform/test_birthday_order_scope.py app/agent_platform/test_birthday_runtime_wiring.py app/security/test_birthday_release.py` → **46 passed**。
- 代码审查：规范轴/规格轴两位独立子代理已完成；必须项已修（提前“已合入”口径、归因/责任历史段标记、mixed 订单用例、变更文件清单、状态与证据回填）。
- 安全审阅：本票为评测/证据更新，不新增产品安全规则；AI 审查不替代 PM/Ringo。
- PR：[#317](https://github.com/DrErwin/hackerthon-bank-agent/pull/317)，head `3710b62`，**已 squash 合入 main `5b4b99d`**（2026-10-26 17:07）；02 合入到本票合入之间的 `evals/mockbank` 5 项红灯窗口已归零。本票不预改产品代码，真实页面/模型/HTTP E2E 与 PM/安全接受不在本票。
- CI：[Repository checks](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/40297023956/job/121485452656) 结论 failure，annotation 明确“job was not started because recent account payments have failed…”，job 未运行、无测试执行证据，不记 CI 绿、非测试失败。

## Verification

从 `backend/` 用本票独立临时目录（不碰共享库）运行：

```powershell
$env:PYTHONPATH=(Get-Location).Path
New-Item -ItemType Directory -Force ../evals/mockbank/evidence/2026-10-26 | Out-Null
python -m pytest -q ../evals/mockbank app/services app/storage --junitxml=../evals/mockbank/evidence/2026-10-26/bank-round-objects.xml -o junit_family=legacy --basetemp=<本票独立临时目录>
python -m pytest -q ../evals/mockbank/test_birthday_round_attribution.py --basetemp=<本票独立临时目录>
```

另按 `birthday-evidence.md` 记录组合定向（本组四项 + 平台订单来源门 + 生日真实装配）实际结果；模型调用 0，真实页面/HTTP 不启动。评测票也走两位独立子代理规范/规格审查，必须项闭合后单独 PR 回交中控。
