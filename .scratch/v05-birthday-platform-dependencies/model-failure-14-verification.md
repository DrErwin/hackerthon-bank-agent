# 平台14受控失败回传验证

2026-10-27。独立实施目录`backend/app/agent_platform/`，实施票[v05-birthday-platform-dependencies/14](issues/14-controlled-model-failure.md)，[PR #337](https://github.com/DrErwin/hackerthon-bank-agent/pull/337)。原B/C报告、输入和期望不改；本票没有新provider/页面运行。

## 实现与证据层

model.py、模型配置、prompt和严格outcome门逐字节保持。`_understand_with_trace`写出原失败审计后，仅保留明确PlanningError安全类型；`handle_message`在创建任务前回既有MODEL_PROPOSAL_FAILED失败ModuleResult。API消费既有分支，无API/契约/安全/birthday源修改，原会话风险披露仍先记录。固定reason是日常话的重新表述与查看原卡提示，不包含资金已处理、账户安全或已拦截保证，也不使用自由模型回复或补造proposal。

原观察码c790带观察分支的未合入父链，尝试自动变基时发现会选入他票，已在无生产改动时撤销；最终只把本票单个诊断提交放到已合335的main30cbe740上。该main为实际生产补修基线，没有把旧B/安全/evals父链重新拼入PR。

## 实际批次

1. 原c790只读诊断：6项为3个严格0-outcome拒绝通过、3个候选提示红例；随后单独API消费接缝探针1通过。这是修复前诊断，不是生产修复通过；[原始分层记录](../v05-model-protocol-diagnosis/README.md)保留。
2. 335新基线，按获批日常话reason重新固定期望：三条原B模型回复只读加载到脚本ChatModel，真实Planner严格门+真实ASGI/Harness；另加空/多outcome的原号与重启回归。修前 **5 failed/3 passed，5.52s，exit1**，其中3个严格检查通过、3个原回复提示及2个空/多outcome提示失败。[原始JUnit无损gzip](evidence/2026-10-27-platform14-before.xml.gz)，解压SHA256 `4FEBE65799FC9F1612A1B45FAFA760FCEEC97A96290F9DA9661DD50FF127E935`。
3. 同样8项修后 **8 passed，6.56s，exit0**；[原始JUnit](evidence/2026-10-27-platform14-after.xml)。直接Planner仍拒绝原3条0-outcome，不将其变成ReplyOnly或资金BLOCK。
4. 新HTTP文件 **3 passed，5.42s，exit0**；[原始JUnit](evidence/2026-10-27-platform14-http.xml)。覆盖原request重复及重启不重新推理、无重复助手消息、0新任务/0submit/0风险gate；原待确认任务、确认和operation保持；公开审计读取仍为model.finished failed、无新task.transition。完整批次另包含0 security.decided检查。

原B外部源SHA256始终 `e8b27e19f75398e02dc64436c75e5af6347296305e1227c07ef241f8f5adbeca`，三条回复只记录字符数/hash/0 tool_calls，不复制正文；观察元数据见[安全摘要](../v05-model-protocol-diagnosis/observation-metadata.json)。本票回放和HTTP的provider调用为0。重启证明针对已持久完成的原消息；原来没有持久结果的未知中断仍按既有恢复规则处理，不伪称已知结果。

## 完整平台回归

主线335后的固定提交 `eff7078a3f3862de444499adcb7bee0c72337c5b`，platform树 `dcfae4956541d753ea515f35cdce93275f70c954`；运行期间源码冻结。命令：

```powershell
python -m pytest backend/app/agent_platform -q --tb=short --junitxml=.scratch/v05-birthday-platform-dependencies/evidence/2026-10-27-platform14-full.xml -o junit_family=legacy
```

**426 passed/13 skipped/0 failed/0 error，368.06s，exit0**。JUnit439个用例、439个唯一`classname + name`，实际通过426项；原有13跳过不计通过，新HTTP3项包含其中。[原始JUnit](evidence/2026-10-27-platform14-full.xml)，SHA256 `10E93BD61B328F4D50A6E6A9B1A18477A7A9AF0CE793C1FB4D1711F25769591E`。这与另行的原3条精确回复回放分开计数，没有重复加总成新的全量。

平台全量覆盖既有合法ReplyOnly、proposal/continuation及安全、恢复分支。本票新增事实是“明确规划失败的受控错误与提示改善”；原B三项Failed保持，不声称模型已遵守工具协议或资金gate已BLOCK。独立两轴、最终CI与用户接受分别记录。

## 最新主线等价核对

全量结束后main仅新增原B证据PR336至 `f4a9872432cbfd9ba13902efc77f467084ede450`，backend无差异。本票自身三提交无冲突机械rebase；交付backend树 `1c70fe538d0a03272c2dd72ad40c87977011bdb3`、platform树 `dcfae4956541d753ea515f35cdce93275f70c954` 与受测eff7078a完全相等，`git diff --quiet eff7078a HEAD -- backend`及main祖先核验均退出0，差异空白检查通过。没有为证据/机械变基再跑一套，也没有引入c790观察分支的旧父链。
