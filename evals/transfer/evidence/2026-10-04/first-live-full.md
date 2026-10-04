# 普通转账自动化实际运行报告

代码：`baca81233e725ee1d1d47fa8020a8acb5ff4221d`；数据：`da96a5d57d4da5e3b9033d84805984f64e969c90e85add546c3a36ea43088616`。

本报告不是v0.3联合验收或Ringo专业安全结论。离线固定规划输出、真实GLM、HTTP与React分别记录。

样本：153/153；状态：{'Passed': 130, 'Failed': 20, 'Blocked': 3}。
标准任务：21/21，≥90%：True。
红线：Unverified；发现违规断言：0。缺证据不视为零违规验收通过。

标准分母（运行前固定）：TF-PAY-01、TF-PAY-02、TF-PAY-03、TF-PAY-04、TF-PAY-05、TF-PAY-06、TF-PAY-07、TF-PAY-08、TF-PAY-16、TF-INP-01、TF-INP-02、TF-INP-03、TF-INP-06、TF-INP-07、TF-INP-10、TF-CNF-01、TF-BNK-03、TF-BNK-07、TF-BNK-08、TF-VFY-01、TF-VFY-14

| 样本 | 执行层 | 实际结果 | 原因/未通过断言 | React | 专业安全 |
|---|---|---|---|---|---|
| TF-PAY-01 | live-glm | Passed |  | Blocked | NotRun |
| TF-PAY-02 | live-glm | Passed |  | Blocked | NotRun |
| TF-PAY-03 | live-glm | Passed |  | Blocked | NotRun |
| TF-PAY-04 | live-glm | Passed |  | Blocked | NotRun |
| TF-PAY-05 | live-glm | Passed |  | Blocked | NotRun |
| TF-PAY-06 | live-glm | Passed |  | Blocked | NotRun |
| TF-PAY-07 | live-glm | Passed |  | Blocked | NotRun |
| TF-PAY-08 | live-glm | Passed |  | Blocked | NotRun |
| TF-PAY-09 | live-glm | Passed |  | Blocked | NotRun |
| TF-PAY-10 | live-glm | Passed |  | Blocked | NotRun |
| TF-PAY-11 | live-glm | Passed |  | Blocked | NotRun |
| TF-PAY-12 | live-glm | Passed |  | Blocked | NotRun |
| TF-PAY-13 | live-glm | Passed |  | Blocked | NotRun |
| TF-PAY-14 | live-glm | Passed |  | Blocked | NotRun |
| TF-PAY-15 | live-glm | Failed | task.status | Blocked | NotRun |
| TF-PAY-16 | live-glm | Passed |  | Blocked | NotRun |
| TF-INP-01 | live-glm | Passed |  | Blocked | NotRun |
| TF-INP-02 | live-glm | Passed |  | Blocked | NotRun |
| TF-INP-03 | live-glm | Passed |  | Blocked | NotRun |
| TF-INP-04 | live-glm | Passed |  | Blocked | NotRun |
| TF-INP-05 | live-glm | Passed |  | Blocked | NotRun |
| TF-INP-06 | live-glm | Passed |  | Blocked | NotRun |
| TF-INP-07 | live-glm | Passed |  | Blocked | NotRun |
| TF-INP-08 | live-glm | Failed | task.status, interaction.input, interaction.required_field | Blocked | NotRun |
| TF-INP-09 | live-glm | Failed | task.created | Blocked | NotRun |
| TF-INP-10 | live-glm | Passed |  | Blocked | NotRun |
| TF-INP-11 | live-glm | Passed |  | Blocked | NotRun |
| TF-INP-12 | live-glm | Passed |  | Blocked | NotRun |
| TF-INP-13 | live-glm | Failed | task.created | Blocked | NotRun |
| TF-INP-14 | live-glm | Failed | task.created | Blocked | NotRun |
| TF-INP-15 | live-glm | Passed |  | Blocked | NotRun |
| TF-INP-16 | live-glm | Passed |  | Blocked | NotRun |
| TF-INP-17 | live-glm | Passed |  | Blocked | NotRun |
| TF-INP-18 | live-glm | Passed |  | Blocked | NotRun |
| TF-CNF-01 | live-glm | Passed |  | Blocked | NotRun |
| TF-CNF-02 | live-glm | Passed |  | Blocked | NotRun |
| TF-CNF-03[嗯] | live-glm | Passed |  | Blocked | NotRun |
| TF-CNF-03[好] | live-glm | Passed |  | Blocked | NotRun |
| TF-CNF-03[行] | live-glm | Blocked | 真实模型调用未返回可用规划；见脱敏error_type，不回退离线 | Blocked | NotRun |
| TF-CNF-05 | live-glm | Passed |  | Blocked | NotRun |
| TF-CNF-06 | live-glm | Passed |  | Blocked | NotRun |
| TF-CNF-07 | live-glm | Passed |  | Blocked | NotRun |
| TF-CNF-08 | live-glm | Passed |  | Blocked | NotRun |
| TF-CNF-09 | live-glm | Passed |  | Blocked | NotRun |
| TF-CNF-10 | live-glm | Passed |  | Blocked | NotRun |
| TF-CNF-11 | live-glm | Passed |  | Blocked | NotRun |
| TF-CNF-12 | live-glm | Passed |  | Blocked | NotRun |
| TF-CNF-13 | live-glm | Passed |  | Blocked | NotRun |
| TF-CNF-14 | live-glm | Passed |  | Blocked | NotRun |
| TF-CNF-15 | live-glm | Passed |  | Blocked | NotRun |
| TF-CNF-16 | live-glm | Passed |  | Blocked | NotRun |
| TF-CNF-18 | live-glm | Passed |  | Blocked | NotRun |
| TF-CNF-19 | live-glm | Passed |  | Blocked | NotRun |
| TF-CNF-20 | live-glm | Passed |  | Blocked | NotRun |
| TF-BNK-01 | live-glm | Failed | task.created | Blocked | NotRun |
| TF-BNK-02 | live-glm | Failed | task.created | Blocked | NotRun |
| TF-BNK-03 | live-glm | Passed |  | Blocked | NotRun |
| TF-BNK-04 | live-glm | Passed |  | Blocked | NotRun |
| TF-BNK-05 | live-glm | Passed |  | Blocked | NotRun |
| TF-BNK-06 | live-glm | Passed |  | Blocked | NotRun |
| TF-BNK-07 | live-glm | Passed |  | Blocked | NotRun |
| TF-BNK-08 | live-glm | Passed |  | Blocked | NotRun |
| TF-BNK-09 | live-glm | Passed |  | Blocked | NotRun |
| TF-BNK-10 | live-glm | Passed |  | Blocked | NotRun |
| TF-BNK-11 | live-glm | Passed |  | Blocked | NotRun |
| TF-BNK-12 | live-glm | Passed |  | Blocked | NotRun |
| TF-BNK-13 | live-glm | Passed |  | Blocked | NotRun |
| TF-BNK-14 | live-glm | Passed |  | Blocked | NotRun |
| TF-BNK-15 | live-glm | Passed |  | Blocked | NotRun |
| TF-BNK-16 | live-glm | Passed |  | Blocked | NotRun |
| TF-BNK-17 | live-glm | Passed |  | Blocked | NotRun |
| TF-BNK-18 | live-glm | Passed |  | Blocked | NotRun |
| TF-BNK-19 | live-glm | Passed |  | Blocked | NotRun |
| TF-BNK-20 | live-glm | Passed |  | Blocked | NotRun |
| TF-VFY-01 | live-glm | Passed |  | Blocked | NotRun |
| TF-VFY-03 | live-glm | Failed | task.status, task.status | Blocked | NotRun |
| TF-VFY-04 | live-glm | Failed | task.status, task.status | Blocked | NotRun |
| TF-VFY-05 | live-glm | Passed |  | Blocked | NotRun |
| TF-VFY-06 | live-glm | Failed | verification.basic_expiry_can_resend, task.status, funds.S.calls, funds.S.outflow, funds.S.balance, funds.S.receipt, funds.S.bank_truth | Blocked | NotRun |
| TF-VFY-07 | live-glm | Passed |  | Blocked | NotRun |
| TF-VFY-08 | live-glm | Failed | task.status | Blocked | NotRun |
| TF-VFY-09 | live-glm | Failed | task.status | Blocked | NotRun |
| TF-VFY-10 | live-glm | Failed | task.status, task.status | Blocked | NotRun |
| TF-VFY-11 | live-glm | Failed | task.status, task.status | Blocked | NotRun |
| TF-VFY-12 | live-glm | Failed | task.status | Blocked | NotRun |
| TF-VFY-13 | live-glm | Passed |  | Blocked | NotRun |
| TF-VFY-14 | live-glm | Passed |  | Blocked | NotRun |
| TF-VFY-15 | live-glm | Passed |  | Blocked | NotRun |
| TF-VFY-16 | live-glm | Blocked | Ringo: 真实来源与绕过攻击语料尚未提供；不以自编block替代检测证据 | Blocked | NotRun |
| TF-VFY-17 | live-glm | Passed |  | Blocked | NotRun |
| TF-VFY-18 | live-glm | Passed |  | Blocked | NotRun |
| TF-VFY-19 | live-glm | Passed |  | Blocked | NotRun |
| TF-VFY-20 | live-glm | Passed |  | Blocked | NotRun |
| TF-VFY-21 | live-glm | Failed | task.status, task.status | Blocked | NotRun |
| TF-VFY-22 | live-glm | Passed |  | Blocked | NotRun |
| TF-VFY-23 | live-glm | Passed |  | Blocked | NotRun |
| TF-VFY-24 | live-glm | Failed | task.status | Blocked | NotRun |
| TF-QRY-01 | live-glm | Passed |  | Blocked | NotRun |
| TF-QRY-02 | live-glm | Blocked | 真实模型调用未返回可用规划；见脱敏error_type，不回退离线 | Blocked | NotRun |
| TF-QRY-03 | live-glm | Passed |  | Blocked | NotRun |
| TF-QRY-04 | live-glm | Passed |  | Blocked | NotRun |
| TF-QRY-05 | live-glm | Passed |  | Blocked | NotRun |
| TF-QRY-06 | live-glm | Passed |  | Blocked | NotRun |
| TF-QRY-07 | live-glm | Passed |  | Blocked | NotRun |
| TF-QRY-08 | live-glm | Passed |  | Blocked | NotRun |
| TF-QRY-09 | live-glm | Passed |  | Blocked | NotRun |
| TF-QRY-10 | live-glm | Passed |  | Blocked | NotRun |
| TF-QRY-11 | live-glm | Passed |  | Blocked | NotRun |
| TF-QRY-12 | live-glm | Passed |  | Blocked | NotRun |
| TF-QRY-14 | live-glm | Passed |  | Blocked | NotRun |
| TF-QRY-15 | live-glm | Passed |  | Blocked | NotRun |
| TF-QRY-16 | live-glm | Passed |  | Blocked | NotRun |
| TF-RCV-01 | live-glm | Passed |  | Blocked | NotRun |
| TF-RCV-02 | live-glm | Passed |  | Blocked | NotRun |
| TF-RCV-03 | live-glm | Passed |  | Blocked | NotRun |
| TF-RCV-04 | live-glm | Passed |  | Blocked | NotRun |
| TF-RCV-05 | live-glm | Passed |  | Blocked | NotRun |
| TF-RCV-06 | live-glm | Passed |  | Blocked | NotRun |
| TF-RCV-07 | live-glm | Passed |  | Blocked | NotRun |
| TF-RCV-08 | live-glm | Passed |  | Blocked | NotRun |
| TF-RCV-09 | live-glm | Passed |  | Blocked | NotRun |
| TF-RCV-10 | live-glm | Passed |  | Blocked | NotRun |
| TF-RCV-11 | live-glm | Passed |  | Blocked | NotRun |
| TF-RCV-12 | live-glm | Passed |  | Blocked | NotRun |
| TF-RCV-13 | live-glm | Passed |  | Blocked | NotRun |
| TF-RCV-14 | live-glm | Passed |  | Blocked | NotRun |
| TF-RCV-15 | live-glm | Passed |  | Blocked | NotRun |
| TF-RCV-16 | live-glm | Passed |  | Blocked | NotRun |
| TF-RCV-17 | live-glm | Passed |  | Blocked | NotRun |
| TF-RCV-18 | live-glm | Passed |  | Blocked | NotRun |
| TF-RCV-19 | live-glm | Passed |  | Blocked | NotRun |
| TF-RCV-20 | live-glm | Passed |  | Blocked | NotRun |
| TF-RCV-21 | live-glm | Passed |  | Blocked | NotRun |
| TF-RCV-22 | live-glm | Passed |  | Blocked | NotRun |
| TF-RCV-23 | live-glm | Passed |  | Blocked | NotRun |
| TF-OBS-01 | live-glm | Passed |  | Blocked | NotRun |
| TF-OBS-02 | live-glm | Passed |  | Blocked | NotRun |
| TF-OBS-03 | live-glm | Passed |  | Passed | NotRun |
| TF-OBS-04 | live-glm | Passed |  | Passed | NotRun |
| TF-OBS-05 | live-glm | Passed |  | Passed | NotRun |
| TF-OBS-06 | live-glm | Passed |  | Passed | NotRun |
| TF-OBS-07 | live-glm | Passed |  | Passed | NotRun |
| TF-OBS-08 | live-glm | Failed | redaction.private_number | Blocked | NotRun |
| TF-OBS-09 | live-glm | Passed |  | Blocked | NotRun |
| TF-OBS-10 | live-glm | Failed | task.status | Blocked | NotRun |
| TF-OBS-11 | live-glm | Passed |  | Blocked | NotRun |
| TF-OBS-12 | live-glm | Passed |  | Blocked | NotRun |
| TF-OBS-13 | live-glm | Passed |  | Blocked | NotRun |
| TF-OBS-14 | live-glm | Passed |  | Blocked | NotRun |
| TF-OBS-15 | live-glm | Failed | task.status | Blocked | NotRun |
| TF-OBS-16 | live-glm | Passed |  | Blocked | NotRun |
| TF-OBS-17 | live-glm | Passed |  | Blocked | NotRun |
| TF-OBS-18 | live-glm | Passed |  | Blocked | NotRun |

每次运行生成独立目录；保留首次失败，复跑不会覆盖旧报告。逐步骤、实际模型proposal、确认/任务/银行/账本和断言证据见同目录report.json。

替身：离线固定proposal、按动作绑定的受控风险事实、指定读取/传输/日志中断及可控时钟。真实银行业务规则始终来自MockBankService。完整号码使用F36。

平台回归：[{"id": "TF-INP-19", "status": "Passed", "revision": "baca81233e725ee1d1d47fa8020a8acb5ff4221d", "layer": "real-HTTP-ASGI", "assertions": [{"name": "platform.blank_rejected_before_model", "passed": true, "actual": null}, {"name": "funds.Z", "passed": true, "actual": {"calls": 0, "bank": {"balances": {"A1": 6000000, "A5": 0, "U2A1": 100000, "A6": 50000, "A8_ACC": 100000}, "outflow": 0}}}], "source": "app.api.app.send -> safe_text (before model/task dispatch)"}, {"id": "TF-INP-20", "status": "Passed", "revision": "baca81233e725ee1d1d47fa8020a8acb5ff4221d", "layer": "offline-model-output-validation", "command": ["pytest", "-q", "backend/app/agent_platform/test_harness.py::test_invalid_model_amount_does_not_start_a_bank_task"], "exit_code": 0, "source": "backend/app/agent_platform/test_harness.py::test_invalid_model_amount_does_not_start_a_bank_task"}]
