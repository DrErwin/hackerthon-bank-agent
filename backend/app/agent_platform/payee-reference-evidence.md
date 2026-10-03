# v03-transfer-eval-fixes/02：受控收款资料引用交付证据

Date: 2026-10-04（Asia/Shanghai）
Status: 已实现并针对性验证；待真人安全批准及合入，03/04接线未完成。
Directory: backend/app/agent_platform/

正式票来源：主工作区 `.scratch/v03-transfer-eval-fixes/issues/02-controlled-payee-reference.md` 及已批准的同组 `spec.md`。规划文件尚未提交，不把它们假称为主线可读能力。此文保存本票可公开审阅的验收摘要与实际结果。

## 范围与验收

仅提供可信后端登记、解析和清理接口；完整手工资料保存在既有受控参数表，普通状态只接收不可猜测引用及银行脱敏展示。必须检查当前有效会话、用户、任务、轮次及资料版本；跨归属、失效引用拒绝。登记经过现有工具权限、安全门和银行核验；拒绝、户名不匹配和技术故障不能返回办理引用。重建保留受控资料，轮次切换使旧资料不可读。接口不授予确认、身份验证或资金执行权限。

后继03转账检查点及04 F36入口尚未接入，02不表示TF-OBS-08整条链通过。不涉及模型修复、提示词、暂缓10、真实GLM批量评测、合并、飞书或联合验收。

## 首次复现

执行原PR51的离线固定proposal CLI，仅选择TF-OBS-08。该CLI固定自己的代码ROOT，因此本次复现运行的是PR51 HEAD `58740f541a6777f87490593a91515e4a2efda28a`，产品基线 `baca81233e725ee1d1d47fa8020a8acb5ff4221d`，不是02修复接入后的HTTP路径。

结果：1 Failed，153样本中的其余152项未运行。完整号码仍命中普通检查点秘密检查；历史失败保留，不以本票新接口测试覆盖或改写它。复现原报告目录为来源评测worktree内 `.mnemon/transfer-evals/20261003T201326243104Z/`，原JSON与Markdown均保留；未打印敏感原文。

先建立新接口的行为测试，首次运行因缺少 `app.agent_platform.payee_references` 收集失败，证明底座此前没有本票要求的公开引用能力；实现后再验证。

## 修复与针对性验证

产品基线：`baca812`；实现提交：`9c63b66`；AI意见修复后代码提交：`7aab914`。每项使用临时应用库与临时模拟银行库，不使用开发演示库。

最终在既有评测Python环境、此worktree的 `backend/` 中执行：

```powershell
python -m pytest -q app/agent_platform/test_payee_references.py app/agent_platform/test_transfer_runtime.py app/agent_platform/test_local_demo.py
```

实际结果：**41 passed，39.31秒**（15引用、16真实转账运行、10本地HTTP组合测试）。使用既有评测worktree的 `.venv/Scripts/python.exe`，产品模块从当前worktree加载；不安装或修改依赖、不连接真实模型。系统Python最初缺少 `langchain_openai`，本地HTTP测试收集失败；改用已有完整环境后通过，不能把首次失败记为通过。

新增测试逐项覆盖：银行脱敏展示同源；引用解析后真实银行重新核验及500元预检查；工厂重建；跨用户/任务/轮次/会话拒绝；错误版本拒绝；换资料及显式清理后旧引用拒绝；错误户名不保留旧资料；银行与存储异常固定错误码；当前轮次重置及会话过期拒绝；越权登记不触及银行、不清理他人记录；工具权限拒绝；真实失败/取消/成功终态任务拒绝；可信会话迁移后新会话读取及旧会话拒绝。核验与预检查没有资金动作。

普通秘密扫描覆盖 `tasks`、`audit_events`、`audit_evidence`、`checkpoints`、`checkpoint_blobs`、`checkpoint_writes`，只报告命中位置。它证明本票登记/解析路径不把原文写入这些表，不能代替03/04接线后的暂停、修改及恢复全链扫描。

仓库链接、变更语法和 `git diff --check` 通过。本票没有重复运行153样本或本地全部后端回归；代码PR仍保留现有CI。三组组合验证和最终离线全量尚未运行。

## AI审查与待批准事项

`code-review` 对固定基线 `baca812` 独立检查Standards与Spec。首轮Standards发现核验直接调用网关、绕过工具权限；已接回现有登记工具、执行器、安全门及审计，并补拒绝测试。Spec建议补真实会话迁移，已补充。最终Standards与Spec独立复审均无剩余阻断发现。

以上均为AI工程审查，不是Ringo真人安全批准或历史PR豁免。当前没有合并授权，安全批准和合入仍待处理。仓库同一人最多两个未合PR，已有PR51占一个名额；本票PR发布后到上限，不能自行叠第三层功能或创建其余票的PR。01、03—09仍未实施，10保持paused。原评测03/04、联合验收12及v0.3状态不提升。
