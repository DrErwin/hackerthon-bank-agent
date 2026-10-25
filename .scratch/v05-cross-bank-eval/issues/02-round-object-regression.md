# 02：跨轮次旧对象边界回归收口

Ticket ID: v05-cross-bank-eval/02

Package: [v05-cross-linkage/packages/06-bank-eval：银行专项验收](../../v05-cross-linkage/packages/06-bank-eval.md)

Spec: [本工作组规格](../spec.md)；责任判断与证据见[v05-bank-round-objects 核查报告](../../v05-bank-round-objects/verification.md)。

Type: 评测

Core scenarios: XL-B01 的跨轮次分支；定义见[共享规格 §5](../../v05-cross-linkage/spec.md)。

Owner: Erwin

Directory: `evals/mockbank/`

Status: blocked — 依赖提供方修复合入；未实施。

Blocked by: [v05-bank-round-objects/02：银行服务与网关按可信轮次校验冻结/订单对象](../../v05-bank-round-objects/issues/02-object-round-services.md)（01 是 02 的传递前置，见 [01](../../v05-bank-round-objects/issues/01-object-round-storage.md)）。

Source: [PR #290](https://github.com/DrErwin/hackerthon-bank-agent/pull/290) 四项 strict xfail；[PR #294](https://github.com/DrErwin/hackerthon-bank-agent/pull/294) 归因；[PR #296](https://github.com/DrErwin/hackerthon-bank-agent/pull/296) 平台订单来源门（已合入）。

## What to build

真实约束满足后，把银行专项的四项已知缺口转成正式回归，并让归因测试不再依赖“D2 可读 D1 对象”这一将被关闭的行为：

1. `test_birthday_bank_eval.py::test_old_round_objects_with_new_operation_are_denied`：
   - 去掉 `xfail(strict=True)` 与 `OldRoundObjectAllowed` 例外类型；
   - 四项分别断言：D2 对 D1 冻结/订单的 B13/B22 读取拒绝（`ACCESS_DENIED`）；D2 新编号核销/释放 D1 冻结拒绝（失败回执，无成功）；
   - 断言六类银行事实（accounts/freezes/orders/order_payments/ledger_entries/bank_operations）除允许的失败回执外不变，无资金移动；
   - 增加同轮次正常对照：D1 读取/核销/释放仍成功，合法订单只付一次。
2. `test_birthday_round_attribution.py`：
   - 该文件此前用 D2 网关读取旧订单/旧冻结来核对“旧订单仍 unpaid、旧冻结仍 500”（`current.gateway.get_order(who=D2, old_order_id)` 等）；对象轮次校验打开后这些读取会变为拒绝。改用原轮次（D1）可信上下文观察（`current.gateway` 与旧 runtime 共用同一银行库文件）或直接银行库事实，保持原产品边界结论与历史证据不变；
   - 不删除任何反例、不把历史失败改成通过。
3. 证据与文档：
   - 重新运行 `evals/mockbank/birthday-evidence.md` 记录的专项命令；分两个口径：①`test_birthday_bank_eval.py` 单文件 41 项（原 37 项 + 4 项转正）全部通过、0 xfailed；②合跑命令按实施后实际节点全绿、0 failed/0 xfailed（2026-10-25 记录为 153 节点，2026-10-26 收集为 175 节点，按实际记录，不写死节点数、不凑数）；
   - 新 JUnit 保存到独立证据目录（如 `evals/mockbank/evidence/2026-10-26/`，目录由本票创建），历史 strict xfail 与归因失败 XML 原样保留；
   - 更新 `birthday-evidence.md`、`round-attribution.md` 的当前结论、运行结果与未覆盖范围；更新 `v05-cross-bank-eval/01`、`round-boundary-gap.md` 与本票状态；
   - 报告明确区分：银行对象层回归通过 ≠ 页面/HTTP/模型 E2E 通过 ≠ B26 整体重置 ≠ 安全专项/真人签核/PM 接受。

## Acceptance criteria

- [ ] 四项原 strict xfail 转为普通断言并实际通过；`--runxfail` 不再出现 `OldRoundObjectAllowed`，也没有以放宽断言/删除用例换绿。
- [ ] 同轮正常冻结→下单→核销→释放、原编号回查、响应丢失恢复、合法订单只付一次继续通过。
- [ ] 专项命令实际结果：单文件 41 项全部通过、0 xfailed；合跑命令按实际节点全绿、0 failed/0 xfailed。
- [ ] 归因测试仍在最新 main 上通过，产品边界/ASGI/内部端口/历史失败证据与结论保持；没有新增“页面可越权”或“安全专项通过”的表述。
- [ ] 只改 `evals/mockbank/` 与银行评测组文档；不改产品代码，不改共享项目跟踪/版本 completion。

## Verification

从 `backend/` 用本票独立临时目录（不碰共享库）运行：

```powershell
$env:PYTHONPATH=(Get-Location).Path
python -m pytest -q ../evals/mockbank app/services app/storage --junitxml=../evals/mockbank/evidence/2026-10-26/bank-round-objects.xml -o junit_family=legacy --basetemp=<本票独立临时目录>
python -m pytest -q ../evals/mockbank/test_birthday_round_attribution.py --basetemp=<本票独立临时目录>
```

另按 `birthday-evidence.md` 记录组合定向（本组四项 + 平台订单来源门 + 生日真实装配）实际结果；模型调用 0，真实页面/HTTP 不启动。评测票也走两位独立子代理规范/规格审查，必须项闭合后单独 PR 回交中控。
