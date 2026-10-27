# v05-bank-reset/01 银行服务验证（2026-10-27）

基线：`152d61d47a3a6fd3c6c1145001a36aeca9a9307c`。实施目录仅 `backend/app/services/`；本组保存规格、票据和结果。服务内部管理接缝已由主代理确认；F30—F32、应用/记忆及平台排空另行实现。

## 实际验证

从本 worktree 的 backend 目录，以已有 Python 3.12 后端虚拟环境运行，PYTHONPATH 指向本 worktree 的 backend：

```powershell
python -m pytest app/services ../evals/mockbank -q --tb=short --junitxml=../.scratch/v05-bank-reset/services-results.xml -o junit_family=legacy
```

最终 **149 passed / 0 failed / 0 skipped，25.07 秒**。JUnit [services-results.xml](services-results.xml) 为 149 tests / 0 failures / 0 errors / 0 skipped，记录时间 2026-10-27 14:26:58 +08:00；SHA-256 `7c0e70ef27f4d9d41dee76665e16d47ee0edd00410deee33c5747eeea1d6f680`。

新增 `test_demo_reset.py` 10 项：固定种子恢复及重启查询、成功原号重放不清新业务、异参/异操作者拒绝、普通/未授权/错轮管理身份拒绝、种子恢复真实 SQLite ABORT 后原子回滚及原号续做、真正 processing 转账等待（只将演示慢等待替换为事件闸，银行提交与账本仍真实）、旧轮资金写拒绝/新轮正常、非法轮次/时间、旧故障清除且成功重放保留新故障。

原基线上先加入首批 5 项新回归，实跑 5 failed，均因正式 `reset_demo` 尚不存在；实施后目标 10 项通过。一次目标初跑将原核验拒绝异常误写为 None，已按现有接口修正断言；未更改核验拒绝实现。实际重置仅作用于 pytest 新建临时数据库，未打开或清理共享演示库与原失败目录。

文档本地链接与 `git diff --check` 通过。没有运行真实模型、HTTP/页面 E2E、完整后端、真人接受或专业安全签核；149 是服务及银行专项，不冒称整体系统通过。

## 公开消费接缝

- `bank.reset_demo(admin, management_operation_id, source_round_id, target_round_id, initial_logical_at)`。
- `bank.get_demo_management_operation(admin, management_operation_id)`；同操作者管理身份可查旧轮结果，未授权或其他操作者拒绝，未找到返回 None。
- `bank.current_demo_round_id`：首次 B26 前 None；第一笔受理绑定原轮，成功后为新轮，重启仍返回。
- 返回 `BankDemoManagementResult`：`management_operation_id/status/source_round_id/demo_round_id/logical_at/error`；status 为 running/succeeded/failed；同号失败可原号续做，已成功只回放。
- `initial_logical_at` 由平台按契约 §6.8 DemoView 与 §7.2/7.3 演示起点传入，必须带时区。银行使用它恢复流水和签约种子，不替平台决定起点。

平台须先停止新业务并排空全部任务（含生日/释放）；银行自己的 processing 防线不代替该屏障。银行成功只表示银行数据库已恢复，应用/记忆/逻辑时钟、旧会话与任务失效和历史审计保留仍由平台协调。管理记录存于银行专有表并保留，动态业务数据及旧挑战按 B26 清除；本票不操作独立审计库。

## 审查与交付

独立 Standards/Spec 审查和最终合入由主代理统一安排，本票尚不代记通过。CI 如因计费未启动仍如实记阻塞；不自合并、不关闭整体重置或银行验收。
