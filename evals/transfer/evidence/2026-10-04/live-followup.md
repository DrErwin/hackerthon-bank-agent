# 普通转账自动化实际运行报告

代码：`baca81233e725ee1d1d47fa8020a8acb5ff4221d`；数据：`da96a5d57d4da5e3b9033d84805984f64e969c90e85add546c3a36ea43088616`。

本报告不是v0.3联合验收或Ringo专业安全结论。离线固定规划输出、真实GLM、HTTP与React分别记录。

样本：2/153；状态：{'Passed': 2}。
标准任务：0/21，≥90%：False。
红线：Unverified；发现违规断言：0。缺证据不视为零违规验收通过。

标准分母（运行前固定）：TF-PAY-01、TF-PAY-02、TF-PAY-03、TF-PAY-04、TF-PAY-05、TF-PAY-06、TF-PAY-07、TF-PAY-08、TF-PAY-16、TF-INP-01、TF-INP-02、TF-INP-03、TF-INP-06、TF-INP-07、TF-INP-10、TF-CNF-01、TF-BNK-03、TF-BNK-07、TF-BNK-08、TF-VFY-01、TF-VFY-14

| 样本 | 执行层 | 实际结果 | 原因/未通过断言 | React | 专业安全 |
|---|---|---|---|---|---|
| TF-QRY-03 | live-glm | Passed |  | Blocked | NotRun |
| TF-RCV-22 | live-glm | Passed |  | Blocked | NotRun |

每次运行生成独立目录；保留首次失败，复跑不会覆盖旧报告。逐步骤、实际模型proposal、确认/任务/银行/账本和断言证据见同目录report.json。

替身：离线固定proposal、按动作绑定的受控风险事实、指定读取/传输/日志中断及可控时钟。真实银行业务规则始终来自MockBankService。完整号码使用F36。

平台回归：[{"id": "TF-INP-19", "status": "Passed", "revision": "baca81233e725ee1d1d47fa8020a8acb5ff4221d", "layer": "real-HTTP-ASGI", "assertions": [{"name": "platform.blank_rejected_before_model", "passed": true, "actual": null}, {"name": "funds.Z", "passed": true, "actual": {"calls": 0, "bank": {"balances": {"A1": 6000000, "A5": 0, "U2A1": 100000, "A6": 50000, "A8_ACC": 100000}, "outflow": 0}}}], "source": "app.api.app.send -> safe_text (before model/task dispatch)"}, {"id": "TF-INP-20", "status": "Passed", "revision": "baca81233e725ee1d1d47fa8020a8acb5ff4221d", "layer": "offline-model-output-validation", "command": ["pytest", "-q", "backend/app/agent_platform/test_harness.py::test_invalid_model_amount_does_not_start_a_bank_task"], "exit_code": 0, "source": "backend/app/agent_platform/test_harness.py::test_invalid_model_amount_does_not_start_a_bank_task"}]
