手工收款资料在原实现的 LangGraph resume 写入中泄露完整号码。现在在首次启动和 resume 持久化前经受控平台登记，只把不可还原的任务绑定引用存进业务状态；银行工具在受控执行器内解析资料。saved/own 路径保持可用，资料或金额变化使旧确认失效。非法金额先被拒绝，保留原引用；户名不匹配进入原任务 waiting_input/PAYEE_MISMATCH 供纠正，不产生可执行目标。

实施票：v03-transfer-eval-fixes/03 — 转账检查点仅保留资料引用（本地 `.scratch/v03-transfer-eval-fixes/issues/03-checkpoint-payee-reference.md`，未提交；关键验收约束见本正文）。范围仅 backend/app/modules/transfer/，TF-OBS-08、手工目标纠正及旧确认拒绝。Depends on PR #52；Draft 以其前序分支为目标，前序合入后需重新整理基线。使用既有公开 StartTransferInput，无公共契约字段变化。涉及隐私、确认与资金路径，仍待真人安全审查与合入批准。

验证：模块原46项测试通过；修复审查发现的拒绝输入生命周期和户名不匹配状态后，手工目标文件9项通过，覆盖首次输入、修改、暂停、重建、checkpoint/checkpoint_blobs/checkpoint_writes/普通日志秘密扫描、同任务纠正、银行零副作用、确认后单次执行及越权引用拒绝。两轴 AI 复审无剩余缺陷。04 API 入口及组合 HTTP 隐私联调尚待，不声明 v0.3 验收。


### 本轮合并授权（2026-10-04）

用户明确指示：“我豁免ringo审批，合并吧”。本 PR 属于本轮转账评测及 01—09 程序修复范围；记录为项目负责人豁免本轮 Ringo 真人审批，不记作 Ringo 已审查，不替代安全专业评测或 v0.3 最终验收。票 10 继续暂停。合并前更新到最新 main 并核验当前提交 CI。
