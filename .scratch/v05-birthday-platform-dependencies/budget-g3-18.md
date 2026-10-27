# 平台18：专用预算输入与G3封存衔接

Status: in_progress
Owner: Erwin（v0.5），中控2026-10-27明确委派
Directory: `backend/app/agent_platform/`
Package: [底座与模拟银行](../v05-cross-linkage/packages/01-platform-bank.md)

## 结果

真实G3生日菜单中选择设置本月个人预算、输入10000元，再通过专用`resume_budget_input`采用时，预算已真实写入；G3发布随后推进任务版本，预算来源的最终completion仍对新任务要求原dispatch版本，误报BUDGET_INPUT_STALE。

本票只修平台原受理与封存来源证明：保留原会话/请求/交互/选项、完整候选digest与dispatch CAS校验，不修改Cross F10 guard，不纯存储seed，不猜新版本等于旧版本加一。G3关联使用原受理的服务端origin UUID，与普通F10客户端请求编号隔离；完成只认该受理的真实封存winner和实际发布版本。已采用的中断按原请求找原winner，不能二次adopt或覆盖后来计划。

## 验证

- P18-01：真实Harness/G3/Cross采用，正常回completion，实际预算只写一次、无资金动作。
- P18-02：同原请求、换run与重启重放原结果；G3已发布而completion CAS中断后只读核实原winner，不再adopt；后来当前状态保留。
- P18-03：异参、错会话/轮次/任务、无专用来源仍拒绝，既有预算来源测试保持。
- P18-04：外部CAS在发布前/后漂移仍拒绝；将本origin失效或移除也不能跳过completion检查、覆盖当前新结果。不刷新dispatch版本或把任意新publication当本次采用。
- P18-05：G3拥有的seal/publication断点只沿原受理封存发布；没有可证明原winner时失败关闭，不新建采用。

使用NoopModel及新隔离库，真实业务采用与G3接缝；不重跑真实模型、不改Cross09原controls、B/C报告、337或16/17释放工作。初始基线main f4a98724；完整平台组合同步至16/17均合入的main c760f0d0后仅运行一次。
