# SEC-L-002 cookie 响应归因与评测修正

日期：2026-10-25。票据：[v05-cross-security/02](../../../.scratch/v05-cross-security/issues/02-cross-security-evidence.md)。中控续派要求先追溯原批准要求，确认过时断言后仅修评测；PR270样例、本次产品规则及原失败证据均不改。

## 原要求与实现沿革

| 依据 | 已有要求 / 事实 | 对本次判定的含义 |
|---|---|---|
| [公共契约 §4.5/F05](../../../docs/contracts/公共契约-2026-09-23.md) | 可识别认证秘密在保存聊天、入模、SSE、日志前处理；无法安全处理可暂停入模并提示专用入口 | 普通聊天拒绝实际会话秘密符合边界；F05的202是正常受理响应，不能要求所有秘密输入都受理 |
| 同契约 §6.4 | 登录凭据使用服务端会话及 HttpOnly Cookie | 测试带值的cookie标记属于会话秘密，不是普通业务数据 |
| [bank-e2e-remediation/05](../../../.scratch/bank-e2e-remediation/issues/05-conversation-dispatch.md) | 实际凭据不落库、不入模型；讨论验证码不误拒，确认/验证继续专用入口 | 没有要求cookie必须脱敏后进入planner |
| [PR234](https://github.com/DrErwin/hackerthon-bank-agent/pull/234)，提交 `5699acb`，依赖 [PR233](https://github.com/DrErwin/hackerthon-bank-agent/pull/233) / `4cc8ab1` | `safe_text` 改用 `has_chat_secret`，实际秘密值在聊天落盘前拒绝；`probe_output`将带值cookie识别为credential | 当前400是已合入的秘密前置拦截，不是本票新增政策 |
| 原评测提交 `3ca78be` | 旧API关键词列表未包括cookie，转为脱敏后202；评测硬编码前三类400、cookie202且脱敏送planner | 原评测锁定了旧实现路径，超出了原用例“秘密出口命中0”的要求 |

结论：这是**过时的评测判定**，本次无需修改API或安全实现。四类秘密前置拒绝符合现行批准范围；它不证明所有真实攻击或普通自然语言输入都能识别。

## 稳定复现与排除其他原因

原命令：`python -m pytest evals/security/test_security_eval.py::test_secret_outlet_scan_probes_categories_separately_without_exporting_values -q --tb=line`。修正前再次失败：评测返回Failed，测试期望Blocked。

按可能性核对：旧评测路径、API误判、格式/会话等无关拒绝。最小HTTP探针不启动业务任务，在独立临时库的有效会话/对话中连续提交3次合成cookie秘密：每次均为 `400 / USE_VERIFICATION_ENDPOINT`，消息/后台消息任务/业务任务数量及银行状态不变，planner调用和银行提交均为0。相同环境正常请求返回202并等待正式确认，资金提交仍为0。

再跑原完整SEC-L-002/v01：四类输入全部到达前置秘密保护，均返回同一准确错误码；模型输入、持久库、聊天历史、普通响应、审计的秘密命中均0，资金写入0。只有“cookie必须202且送脱敏planner”这条旧断言失败。由此排除随机400、会话失效、格式错误、模型失败和资金执行问题。

归因原始记录按日期gzip归档于[运行台账](../run-log.md)。之前152通过/1失败的全目录报告和脱敏复现保留原样，不重写历史结论。

## 评测修正与防误绿

仅修改 `evals/security/security_runner.py` 与相应测试：

- 四类秘密均须400，且错误码均为 `USE_VERIFICATION_ENDPOINT`；普通400或503不能通过。
- 逐请求比较消息、后台消息任务和业务任务计数，原任务、可信确认记录、验证挑战及银行状态必须保持不变；planner不得取得任何探针输入。
- 保留原有持久化/聊天/响应/审计等秘密扫描，不删除负面断言。
- 增加故障回归：真实请求到达API后，将观察响应改成400/INVALID_ARGUMENT或503/DEPENDENCY_UNAVAILABLE，评测都必须Failed，防止“只要请求没成功就算安全”。

这些检查验证当前受测API的前置拒绝行为。SEC-L-002整体仍因真实模型、部分日志/导出/SSE等观察层缺失保持Blocked；局部断言通过不等于完整安全专项完成。Standards/Spec双子代理审查均无必须项，运行结果另按实际归档。

## 实际结果

- 修正前原测试重复失败；3次最小HTTP均精确拒绝且零副作用，原完整探针只失败于旧cookie202判定。
- 修正后定向3测试通过（含两种错误拒绝对照）；最终加强确认/验证挑战不变比较后，全目录 **155 passed / 0 failed / 0 collection errors**。全目录报告记录起止时间，耗时约275秒。
- 修正后原SEC-L-002/v01：10观察断言全部通过、四类准确400/错误码、四次状态不变、planner输入0、各出口秘密命中0、资金写入0；用例整体仍Blocked。
- 归因、修后局部与全目录正本均gzip入库，解压SHA256记[运行台账](../run-log.md)。原152/1失败批次未覆盖。
