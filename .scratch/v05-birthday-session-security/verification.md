# 生日跨会话安全撤离：局部证据

Ticket: [v05-birthday-session-security/01：未提交生日动作跨会话撤离](issues/01-session-retirement.md)
Date: 2026-10-27
Base: `0b72b0a1c2ee7a95367a33f25d1a40eeea2cd880`
Branch: `codex/v05-birthday-session-security`
Status: 实现与局部回归完成；独立审查、合入和Cross消费尚待

## 修复前后

原Cross09组合探针commit `4af3d4b06f01cfe085d9a8a45dd94893f0a6bce2`的1 failed/1 passed归原消费者工作区保留，本票未覆盖或改写。它证明旧卡拒绝和新grant身份冲突均真实存在，不是新会话恢复成功。

本票先建3个回归；首轮因测试未建立task外键所需的session而失败，更正隔离夹具后，**3 failed**均为缺`begin_session_retirement`。实现后原G2与初始新用例31通过，扩边界后61通过；以下最终组合包括后续全部37项新检查，不累加这些子集。

## 最终组合

从隔离worktree的backend目录执行，已装依赖解释器只复用安装，PYTHONPATH导入当前源码：

```powershell
$env:PYTHONPATH=(Get-Location).Path
& 'D:/hackerthon-bank-agent/backend/.venv/Scripts/python.exe' -m pytest app/security app/agent_platform/test_birthday_session_recovery.py app/agent_platform/test_birthday_runtime_wiring.py app/agent_platform/test_birthday_edit_handoff.py app/agent_platform/test_birthday_edit_continuation.py -q --tb=short --junitxml=../.scratch/v05-birthday-session-security/security-results.xml -o junit_family=legacy
```

**599 passed / 0 failed / 0 errors / 0 skipped in 164.06s**：security 527（其中新37），既有生日provider 72。见[JUnit](security-results.xml)，SHA256 `88b94fb6489a389218606fbd12a589bd8dabc1ac140cba4a87dde9c7081905b9`。链接脚本与`git diff --check`通过；提交前fetch仍为上方base。

## 关键行为与局限

- 同一应用库的真实Task/Session/安全状态，validator在begin/seal两次接收事务connection；从当前或历史确认核对原绑定，持久源/目标session。同参幂等，跨主体/任务/轮次/session、旧确认版本、参数/资源变化或任务CAS变化拒绝；非bool/依赖异常不当安全。
- processing/completed/unknown claim均拒绝begin；begin后原claim抢先将retirement置conflict，seal不能新签。active冻结不能当未提交。任务终止在两边界均拒绝，普通G2入口不能绕过跨会话validator。
- 审计失败使seal和原pending授权失效一起回滚；同号重试只产生一次封存/审计。审计目标为S2，原绑定保留S1，策略版本`v05-birthday-session-retirement-1`；重启可按原attempt回读。
- 新增4个真实隔离银行场景：pending挑战真实退役后旧code/start_face/重建挑战拒绝，旧grant/确认/claim/bind不能复活；passed/failed/expired挑战的退役均由银行拒绝，不伪造sealed。旧挑战行/确认历史不改写。
- 正向新attempt使用新的operation/revision、新会话确认与新银行双因子记录后恰一笔冻结；旧operation仍not_found、原pending授权invalid、新授权active、冻结总额50000分。该测试在claim状态接缝显式提供测试ALLOW决定，银行授权检查/验证是真实的；独立gate的完整验证规则由既有安全回归检查，不能把此测试写成完整真实模型资金安全门验收。

## 消费方前置

平台必须在任何新check/新卡之前冻结原发布事实。`recovery_validator(connection, context, binding)`是后端可信只读检查，在同一个connection核对目标任务/当前轮次/原attempt/发布CAS与参数快照；不允许客户端或模型提供True，也不能只用`_task_terminated`。

银行proof只能取真实gateway旧attempt退役事实；该银行接缝按user/task/round核验，消费者可使用已认证目标TrustedContext，无需伪装旧会话。安全sealed之后，由平台另票创建唯一关联新attempt并重新确认/验证；本票不分配新operation、不修改Cross或平台SOP。已提交/未知/active路径只能保持原号观察或既有真实收尾。

本轮真实模型0次、浏览器/截图未执行、后端全量未跑、CI尚无通过结论；未操作共享库，未运行96分类，未比较模型，未改比赛资料，未关闭#160或代签本人安全接受。599是程序回归，不是原Cross09缺口已闭环。
