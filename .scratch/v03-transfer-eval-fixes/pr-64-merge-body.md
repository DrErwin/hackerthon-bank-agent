流程中途异常原先可能保留过时waiting_approval；修改500元为600元后，图已保存新operation，故障TaskView却仍显示旧operation/500元。真实HTTP先复现50000 !=60000，再利用平台已有逐步观察接缝修复，全部改动保持agent_platform目录。

在审计写入前投影最近已提交节点输入为既有脱敏TransferTaskView，故障时保存该当前事实及可合法取得的检查点引用。会话过期保留已授权引用，不绕过权限或新增银行读取；正常返回的确定结果先持久化，完成日志失败不改写成功事实。

Ticket: v03-transfer-eval-fixes/09（本地票未发布）；场景TF-QRY-08、TF-OBS-15/16及修改金额故障。基线baca812，未改公共契约或银行规则，涉及审计/安全恢复。

验证：5 HTTP故障/恢复测试通过，52 runtime/harness直接相关回归通过；既有三个真实评测场景最终Passed，固定proposal/真实HTTP/隔离银行。覆盖collect/precheck/security三处故障、重建金额/operation一致、旧确认拒绝/零资金调用；中途过期旧401/停止查询/新登录只查原operation；银行已成功后日志失败不新增流水。Standards/Spec独立AI复审原P2已解决，无剩余阻断。

此前跨目录补票提案已撤回：复现后确认平台现有接缝足够。专业安全批准与合入仍待，最终统一组合程序结果见下文；10暂停，未跑GLM，未授权合并。具体证据见backend/app/agent_platform/fault-snapshot-evidence.md。


最终隔离01—09组合验证已完成：完整backend app326 passed（317.14s）、MockBank14 passed（1.07s）；完整离线153样本147 Passed/6 Blocked，0 Failed/0 Error。Blocked为OBS03—07未提供实际React构建和VFY16专业攻击来源材料缺失；标准21/21、D2迁移后问询8/8均是固定proposal层，不是GLM结论。总体红线仍Unverified、NotAccepted，CLI因Blocked返回1。

实际组合基线04/0e540af（含02/461d539、03/6d53860）+05/e23df72+06/eca0ddf+07/5c21031+08/2bf775a+09/f0a1967+01/44bee0b，逐票补丁及67产品/评测文件SHA256保留在隔离worktree assembly-manifest.json，报告验证源码未变。main仍baca812，不能把HEAD0e540af独立当整个组合。PR64/f0a1967当前Repository checks SUCCESS。真人安全批准、合入、React证据、10模型问题及v0.3验收仍待，未跑GLM或合并。


### 本轮合并授权（2026-10-04）

用户明确指示：“我豁免ringo审批，合并吧”。本 PR 属于本轮转账评测及 01—09 程序修复范围；记录为项目负责人豁免本轮 Ringo 真人审批，不记作 Ringo 已审查，不替代安全专业评测或 v0.3 最终验收。票 10 继续暂停。合并前更新到最新 main 并核验当前提交 CI。
