# v03-transfer-eval-fixes/09：故障任务快照证据

基线：baca812；改动仅backend/app/agent_platform/。未改模块公开契约、未跨目录实施补票。

先复现：真实HTTP任务500元→600元，security NODE_STARTED审计故障。图已提交60000分/新operation，旧TaskView仍50000分/旧operation。定向命令在修复前1 failed（50000 != 60000，6.01秒），没有凭审查推断就增加模块能力。

根因：流程正常返回前的技术异常沿用previous.data；正常返回后也先写完成日志再保存结果，留下过时快照。平台已有TracedTransferWorkflow._step，可在审计之前观察已提交节点输入；仅投影既有TransferTaskView脱敏字段到本次RunTrace。异常时使用该当前事实，有权限时保存当前检查点引用，会话过期时保留最后已授权引用，不绕过权限或新增银行读取。已正常返回的确定结果先持久化，再写完成日志。

最新验证：test_fault_snapshot.py 5 passed（23.18秒）；包括collect/precheck/security三个日志故障位置、TaskView与检查点金额/operation一致、重建继续新确认、旧确认拒绝、资金调用0；中途会话过期旧HTTP401且只读一次、新登录重建仅查询原operation；银行已经完成后的完成日志故障仍保存succeeded，重启不新增流水。test_transfer_runtime.py及test_harness.py直接相关52 passed（47.15秒）。原执行开始审计失败测试同时断言零security_executions、零银行流水、持久待核实并重建沿原operation继续。

真实既有evals/transfer场景TF-QRY-08、TF-OBS-15、TF-OBS-16最终定向均Passed；产品强制预载本工作树app.api.app，评测源码PR59/44bee0b，固定proposal/真实HTTP/隔离银行。报告在本worktree .mnemon/ticket09-final/report.json和report.md，历史探测及失败保留；不冒充main、GLM或完整153。

Standards及Spec独立AI复审：原快照P2已解决，无剩余阻断。专业安全批准、合入和最终统一程序验证仍待；10仍暂停。此前模块只读快照补票提案因现有平台接缝足够而撤回，没有实施额外票。
