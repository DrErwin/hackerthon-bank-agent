# 平台18：预算来源/G3完成验证

2026-10-27。[实施票18](issues/18-budget-g3-completion.md)，[PR #344](https://github.com/DrErwin/hackerthon-bank-agent/pull/344)。仅agent_platform与本组材料；Cross09原controls.xml、B/C固定报告和模型/prompt均未修改。

## 已验证行为

真实G3生日菜单→设置本月预算→10000元→专用resume_budget_input，实际预算采用仅一次。原dispatch/候选digest校验保留，G3预留还绑定实际source revision；completion接受同调用的原source及真实publication引用/摘要/版本，不猜G3推进了几版。G3关联使用服务端origin UUID，与普通F10客户端编号隔离。

丢失completion时只回原origin封存winner或Cross核实的旧sealed attempt，原号/换run/重启不再adopt且后继当前计划保留；seal/publish私有pending沿原受理及严格CAS收尾。无持久winner保持失效、不重建采用。修改限额/不采用不产生预算采用。外部CAS无论修改版本、失效还是移除本origin，均不能跳过guard或覆盖新result。

## 真实红绿与定向批次

- 初始正常红例 **1 failed/8.90s**，预算v1已真实写入、adopt一次，却在completed_snapshot抛BUDGET_INPUT_STALE；[原始JUnit无损gzip](evidence/2026-10-27-platform18-before.xml.gz)，解压SHA256 `83C85BB1FAB835CAF63CE0AE211BF9C6176276E7650CAF38E088B31730CB03A5`。
- G3已发布、completion CAS中断，当前计划未/已推进两种回查：**2 failed/1 passed，16.54s**；[原始红例](evidence/2026-10-27-platform18-recovery-before.xml.gz)。修后原35来源+3个真实G3 **38 passed/28.59s**，再扩展为原35+9个G3 **44 passed/56.24s**；[38项](evidence/2026-10-27-platform18-recovery-after.xml)、[44项](evidence/2026-10-27-platform18-focused.xml)。
- 之后G3文件 **11 passed/58.20s**，修改/不采用另 **2 passed/11.29s**；[11项](evidence/2026-10-27-platform18-final-focused.xml)、[2项](evidence/2026-10-27-platform18-choices.xml)。一次中间正常路径已完成，但测试误要求message含选项文字，**1 failed/35 passed，17.39s**单列[原报告](evidence/2026-10-27-platform18-happy.xml.gz)；修为检查真实继续选项，未改业务文案，不算新的业务失败。
- 自查外部CAS将origin invalidated/移除：**2 failed/8.80s**，旧result实证覆盖外部新result；[原始红例](evidence/2026-10-27-platform18-origin-cas-before.xml.gz)，解压SHA256 `CBE721671C21E9AA0D77E3BC5039A07DC9A4E035C3EBF2D650C99824D623F606`。前置active原调用完整性检查后，15真实G3+原35来源 **50 passed/49.66s**；[原始JUnit](evidence/2026-10-27-platform18-origin-cas-after.xml)。

以上批次不重复加总。均为NoopModel、新隔离库，真实Harness/G3/Cross与实际预算采用；没有纯预算存储seed或真实模型重跑，也不替代Cross09完整会话恢复验收。

## 最终完整平台组合

基线 `main@c760f0d0e490db1bee22b181678ce7e869eb5915` 已含335/337/339、安全17（342）与平台16（343）。18的初次6f5f7ba5完整批次为补相位CAS缺口主动中止，最后整行进度78%，exit1且无完整XML；它不是通过或产品测试失败，不用后来的结果覆盖该记录。

最终补修源码固定 `a45407e37378f7ba870d987e4afe2b510be7806b`，backend树 `9bc8b225b76fd5ccaf9c06cdc5667bcdf1e86110`、platform树 `308749342d77026d44c514d771f274db8b0fdbd1`；运行期间源码冻结，结束后diff核对无改动。命令：

```powershell
python -m pytest backend/app/agent_platform -q --tb=short --junitxml=.scratch/v05-birthday-platform-dependencies/evidence/2026-10-27-platform18-final-full.xml -o junit_family=legacy
```

**445 passed/13 skipped/0 failed/0 error，421.87s，exit0**。JUnit458节点且唯一458，实际通过445；15新G3与35既有来源包含其中，原13跳过不算通过。[原始完整JUnit](evidence/2026-10-27-platform18-final-full.xml)，102454字节，SHA256 `7D2463FB8140AEB029C7BD4500B3A1B965C846F50F251EDFE545E5A636ED115B`。

Standards与Spec在a454源码独立增量审查均0必须项。最终只补证据文档，不改受测backend/platform树；CI与合入由中控核对。该受测树不含后继19/20/21或Cross09新消费者，不把它们视为同一组合；中控另安排最终backend集成。没有真人安全签核、页面或新真实模型批的接受结论。
