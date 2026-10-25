# 生日跨轮次边界：真实装配只读归因

Ticket: [v05-cross-bank-round-attribution/01：生日跨轮次边界的真实装配归因](../../.scratch/v05-cross-bank-round-attribution/issues/01-round-boundary-attribution.md)。来源：[PR #290](https://github.com/DrErwin/hackerthon-bank-agent/pull/290) 的四项已知失败；原PR、blocked状态与用例保持不动。

## 结论

原探针证明的是银行内部在测试放行下可使用旧对象。真实装配多了会话、当前轮次、任务及限定授权检查：**旧会话/旧任务不能直接继续；未持执行claim的直接写入被拒绝。** 但真实内部生日付款端口仍接受“当前轮次任务 + 已知旧订单编号”，即使走真实确认与双因素验证，也没有额外核对订单来自当前获准任务/轮次。

这是一项可重复的内部资源范围缺口，**尚未证明普通页面或正常HTTP输入能把旧订单编号送入此端口**。原四项银行边界失败不能直接改称产品越权，也不能因上游有门就删除或改成通过。

## 基线与方法

- 2026-10-25，主线 `9a479ea4414635772fdb723c02b0fc70b76a1a55`。独立worktree/分支，唯一实施目录 `evals/mockbank/`；不修改任何业务实现。
- 真实 `build_runtime`、`BirthdayRuntime`、`SecurityGate`、`DeterministicExecutor`、SQLite安全状态、确认、验证码/模拟人脸、网关与银行/存储。
- 仅模型连接器替换为仓库已有脚本模型；API建任务用一次脚本候选，其余端口探针模型调用为0。无外部模型请求、无页面、无真实TCP服务；HTTP为ASGI TestClient。
- D1通过真实端口确认/验证创建冻结500和未付花订单199，关闭后以**相同临时库、配置改D2**重建真实装配。此操作不是正式B26重置，未恢复种子或删除旧对象。它专门回答“同库换轮次”的问题，不能冒充受支持的完整重置路径。

## 可达性及实际结果

| 路径 | 观察 | 能证明什么 |
|---|---|---|
| RA01 旧cookie→真实API | D1任务GET先200；D2同库重启后旧cookie读会话401；新登录D2，旧任务GET/resume均404 | 不能靠旧cookie或旧task_id从API续办；未证明所有API入口无缺陷 |
| RA02 当前真实网关、无执行claim | 用D2上下文/新编号直接核销或释放D1对象均ACCESS_DENIED，银行事实不变 | PR290常量测试授权的写入结果不能外推到真实网关 |
| RA02 旧D1上下文→真实生日端口 | capture_check与finalize均在memory active-round检查抛STALE_ROUND，尚未提交银行；另独立调用实际SecurityGate亦BLOCK/ACCESS_DENIED | 实际运行链有上游旧轮次失效门；不是bank自身在拒绝 |
| RA03 D2上下文引用D1限定释放授权/B14原操作 | 安全状态读取旧授权ACCESS_DENIED；B14查旧冻结操作ACCESS_DENIED | 新任务不能靠旧限定授权或旧操作编号取得权限 |
| RA03 当前D2任务→内部capture端口，传入已知D1订单 | D2先真实冻结500；订单付款走新的真实确认、双因素及执行claim，支付D1花订单199成功；D1原冻结仍500，D2冻结核销199、剩301 | 内部端口未绑定订单来源；未使用常量授权、未伪造claim；也未从外部产品输入注入旧order_id |
| RA04 B13/B22 | gateway直接只传user_id；本轮D2内部读旧冻结/订单仍成功。birthday运行gate未注册这两个读handler，app路由没有直接冻结/订单查询端点 | 不能把直接gateway读取当成已开放的模型/HTTP读接口 |

限定释放还有第二层显式当前轮次检查（`birthday_release.py:560`）：旧授权所属轮次与current_demo_round不同则BLOCK/STALE_ROUND。本次真实端口调用更早被memory轮次门拒绝，因此这层记录为**静态核对**，不把它冒称本次已到达的分支。

## 具体路径与原规则归属

1. [ApiService](../../backend/app/api/service.py) `identity:144`从当前配置轮次查会话；`link:201`限定当前用户/轮次任务。HTTP的可信上下文来自服务端，不接受普通请求自报轮次。
2. [TransferRuntime](../../backend/app/agent_platform/transfer_runtime.py) `_task:455 → MemoryAdapter._scope`核对active round；[BirthdaySecurityPolicy](../../backend/app/security/birthday_policy.py) `authorize_tool:117`核对当前用户/轮次。它未核对订单来源，平台 `_check/_execute`的ActionDescriptor.resource_refs均为空。
3. [BirthdayRuntime](../../backend/app/agent_platform/birthday_runtime.py) `capture_handler:180`通过本任务freeze操作的B14取得freeze_id，因而不能由capture入参直接指定任意旧冻结；`_capture_parameters:484`直接接收order_id，没有同样的订单创建操作核对。
4. [真实编排](../../backend/app/modules/cross/birthday.py) `:497`把银行创建回执中的order_id存入本任务orders，`:511/:553`取该记录付款。普通响应没有一个已确认可用的“任意旧order_id付款”入口。本次没有覆盖所有畸形输入/恢复组合，因此结论是**未证实外部可达**，不是已证明绝对不可达。
5. [真实claim授权](../../backend/app/security/birthday_release.py) `authorize_birthday_write:166`要求本用户/轮次/任务、operation/action和processing ALLOW claim；正常购买没有独立订单轮次校验。银行[对象查找](../../backend/app/services/mock_bank/birthday.py)按user_id，操作编号本身另按user/round隔离。

现行已定规则：

- [公共契约 §6.3及任务视图约定](../../docs/contracts/公共契约-2026-09-23.md)：登录身份由服务端取得，task_id查询/resume不得跨轮次（任务视图段）；§6.9资源读取由**平台关联任务/会话记录**核验轮次、用途及获准引用范围，旧轮次普通资源不可继续办理。
- [安全附件 §2](../../docs/contracts/安全与审计字段-2026-09-24.md)：先验可信身份与资源归属，无权引用直接拒绝，不能补确认来换权限；§3.1限定释放只覆盖同用户/任务/轮次/原账户，清空本轮后旧授权失效。
- [银行附件 §2/§4](../../docs/contracts/银行接口字段-2026-09-24.md)：业务写经统一执行器，身份由服务端注入；银行验证原冻结归属、订单所属用户/商户/金额和防重；B13/B22输出及参数中没有独立对象轮次字段。这不能推导银行永不需要轮次后盾，但原文也不足以让评测方擅定“所有银行对象必须新增round字段”的方案。
- 公共契约§7.3/B26规定底座协调、银行及应用均重置完成后才能开始新轮。当前真实app无F30/F31路由，当前local_demo把轮次绑定配置值；同库仅改配置不等于该受支持重置流程。

因此：**已有明确的上游失效与资源范围责任；最小闭合先归平台装配，安全侧复核现有规则。银行是否需要独立对象轮次字段/后盾由负责人另行确认，不能用本次探针替代裁定。**

## 最小修复票建议（未实施、未正式建实施票）

| 优先 | 提供目录 | 最小建议与验证 |
|---|---|---|
| 1 | `backend/app/agent_platform/` | 在生日付款执行前，以当前任务已有的order创建操作与B14真实回执核对order_id及当前获准范围；新D2任务即使持有已知D1订单，也应在确认前/提交前按现有无权引用规则拒绝，零扣款。保留正常本任务订单与原号回查路径。不复制银行金额/商户规则。 |
| 复核 | `backend/app/security/` | 核对上述平台资源证明是否足以满足现有安全附件§2、读handler未来注册时如何使用resource_refs；只有确需改安全实现时再拆单目录票，不预建无需求抽象。 |
| 已有正式缺口 | `backend/app/agent_platform/`，必要API/银行/存储各自分票 | 按既定B26/F30—F32完成停收、排空、整体重置及旧授权失效；不能把改config后重启当成功重置。先由中控核对已有票/版本例外，不重复建立大票。 |
| 待负责人裁定 | `backend/app/services/` / `backend/app/storage/` | 是否再以对象来源操作/轮次提供银行独立拒绝作为后盾；若需要，按契约变更流程及单目录票落实。当前不把模式迁移当作已经决定。 |

## 运行与审查

```powershell
cd backend
$env:PYTHONPATH=(Get-Location).Path
python -m pytest -q ../evals/mockbank/test_birthday_round_attribution.py --tb=short --junitxml=../evals/mockbank/round-attribution-results.xml -o junit_family=legacy
```

初轮探针构造有两处纠正：resume只接受request_id（去掉多余choice，避免400在权限判断前阻断）；旧上下文实际先被memory的STALE_ROUND阻断，已改按观察记录，未改业务。最终含旧释放授权/B14补充检查实跑 **3 passed in 14.28s**。这里通过的是“归因断言符合实际”，不是跨轮次缺口已经修复。[原始JUnit](round-attribution-results.xml)。子代理复核及PR状态见本票。

相关原测试另跑 **4 passed, 32 deselected in 18.50s**：真实生日完整链、花付款后停止、无装配网关拒绝，以及`test_stale_round_authorization_cannot_finalize`。最后一项是原安全组件Rig单测，验证finalizer自身的显式STALE_ROUND分支；不冒称本轮真实端口越过了更早的memory轮次门。

独立Standards复核0项必须修复，独立复跑3 passed in 14.24s；Spec/真实性复核0项必须修复，独立复跑3 passed in 13.32s。Spec建议修正文件开头“模型从不被调用”的措辞，已改为“无外部模型请求、API使用一次脚本响应”，不改变运行行为。本票只读归因完成，原专项与跨轮次验收仍blocked。

交付：[PR #294](https://github.com/DrErwin/hackerthon-bank-agent/pull/294)，未自行合并。实查head `74e9471` 的[Repository checks](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/40168942779/job/121095667265)因账号付款/额度问题未启动，记为CI环境阻塞；新增归因文件也未包含在现CI显式旧银行评测命令中，不能以CI绿替代本轮3项实跑。当前分支rebase只新增主线文档，运行实现与测试基线相同。
