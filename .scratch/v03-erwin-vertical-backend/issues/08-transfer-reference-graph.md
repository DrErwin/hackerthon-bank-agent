# 08：实现普通转账参考子图

Type: task\
Status: resolved\
Merged PR: #9\
Owner: Erwin（临时实现）\
Directory: `backend/app/modules/transfer/`\
Blocked by: 02、07\
Integration dependency: 04\
Review: 梁爽负责业务审查，Ringo 审查资金执行接缝\
Unlocks: 09

## 业务目的

把冻结 PRD 的普通转账 14 步流程做成可暂停、可恢复、可测试的 LangGraph 子图，成为后续业务接入框架的参考样例。

## 事实来源

- `docs/prd/01-智能转账-PRD-2026-09-23.md`
- `.scratch/transfer-agent-framework/spec.md`

## 交付

- 普通转账公开能力、模块声明、任务 State 和节点路由。
- 信息补齐、候选消歧、账户核验、预检查、安全检查、确认、验证、提交与结果回查。
- 等待输入、等待选择、等待确认和等待验证的暂停点。
- 取消、修改、明确失败、处理中、结果未知和恢复分支。
- 私有工具声明及模块内 stub 测试。

## 验收

- PRD §5.3 的 14 步业务含义全部可达，没有另造简化流程。
- 同名候选由用户选择，模型不能代选。
- 金额、账户或收款人变化后旧确认失效，并重新走必要检查。
- 只读查询按 PRD 有限重试；写操作结果未知时只查询原 `operation_id`。
- 子图不直连银行存储、不复制余额、限额或风控规则。
- AF01—AF10 在 stub 层有可重复测试，真实联调时沿用相同公共接口。
- 梁爽确认业务流程没有走样后，本票才可标记完成。

## Handoff

子图公开入口稳定后，将 09 改为 `ready`；04 就绪后替换 stub 完成真实银行联调。

## Comments
