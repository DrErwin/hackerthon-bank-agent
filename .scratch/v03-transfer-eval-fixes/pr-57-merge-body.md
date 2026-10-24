验证服务出错时，原API返回503但任务仍保留旧waiting_approval。现在验证写入及挑战读取的技术故障保存原任务needs_attention快照，错误和存储不含秘密及异常原文。未知写入绑定原challenge/submission/method，只允许原提交幂等恢复；后续读取故障不会覆盖该身份。银行已保存而应用未绑定时，仍读取原结果。原提交过期后重新核对银行事实并交既有安全门处理，避免卡在未知状态；API不自判中风险终止规则。

实施票：v03-transfer-eval-fixes/08 — 验证HTTP技术故障发布待核实状态（本地 `.scratch/v03-transfer-eval-fixes/issues/08-verification-error-task-state.md` 未提交，关键约束见本正文）。仅backend/app/api/，TF-VFY-12/TF-OBS-10及直接受影响恢复/过期对照。独立main基线。完整基础过期重发依赖PR #53银行修复，中风险最终failed组合依赖PR #55安全规则；本PR不复制它们。公共契约字段不变，涉及秘密、审计与验证，仍待真人安全审查及合入批准。

验证：原评测HEAD58740f5强制预载原API后两类真实故障均复现task仍waiting_approval。最终6项故障测试通过，覆盖银行未保存/已保存结果、连续GET故障、原submit限制、GET/POST挑战读故障、basic码及mediumface未知后过期核实。最新独立基线6项故障及12项直接相关回归共18项通过。05/06/07/08隔离组合的20项测试通过（基线eca0ddf、平台5c21031、API工作文件SHA256记录于本地组合manifest）；不当作main合入或全量版本验收。两轴AI最终复审无剩余缺陷，真人安全审批和完整集中矩阵仍待。


### 本轮合并授权（2026-10-04）

用户明确指示：“我豁免ringo审批，合并吧”。本 PR 属于本轮转账评测及 01—09 程序修复范围；记录为项目负责人豁免本轮 Ringo 真人审批，不记作 Ringo 已审查，不替代安全专业评测或 v0.3 最终验收。票 10 继续暂停。合并前更新到最新 main 并核验当前提交 CI。
