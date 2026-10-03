# 普通转账自动化实际运行报告

代码：`baca81233e725ee1d1d47fa8020a8acb5ff4221d`；数据：`cdf0ba9436059bc3b5a8716a9aa46dcd96d244a079ff74eeb700e029d3bf3e79`。

本报告不是v0.3联合验收或Ringo专业安全结论。离线固定规划输出、真实GLM、HTTP与React分别记录。

样本：153/153；状态：{'Passed': 118, 'Failed': 25, 'Error': 4, 'Blocked': 6}。
标准任务：19/21，≥90%：True。
红线：Unverified；发现违规断言：0。缺证据不视为零违规验收通过。

标准分母（运行前固定）：TF-PAY-01、TF-PAY-02、TF-PAY-03、TF-PAY-04、TF-PAY-05、TF-PAY-06、TF-PAY-07、TF-PAY-08、TF-PAY-16、TF-INP-01、TF-INP-02、TF-INP-03、TF-INP-06、TF-INP-07、TF-INP-10、TF-CNF-01、TF-BNK-03、TF-BNK-07、TF-BNK-08、TF-VFY-01、TF-VFY-14

| 样本 | 执行层 | 实际结果 | 原因/未通过断言 | React | 专业安全 |
|---|---|---|---|---|---|
| TF-PAY-01 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-PAY-02 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-PAY-03 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-PAY-04 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-PAY-05 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-PAY-06 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-PAY-07 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-PAY-08 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-PAY-09 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-PAY-10 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-PAY-11 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-PAY-12 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-PAY-13 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-PAY-14 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-PAY-15 | offline-real-services | Failed | task.status | Blocked | NotRun |
| TF-PAY-16 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-INP-01 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-INP-02 | offline-real-services | Failed | redaction.credential | Blocked | NotRun |
| TF-INP-03 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-INP-04 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-INP-05 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-INP-06 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-INP-07 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-INP-08 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-INP-09 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-INP-10 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-INP-11 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-INP-12 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-INP-13 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-INP-14 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-INP-15 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-INP-16 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-INP-17 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-INP-18 | offline-real-services | Failed | reply.saved | Blocked | NotRun |
| TF-CNF-01 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-CNF-02 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-CNF-03[嗯] | offline-real-services | Passed |  | Blocked | NotRun |
| TF-CNF-03[好] | offline-real-services | Passed |  | Blocked | NotRun |
| TF-CNF-03[行] | offline-real-services | Passed |  | Blocked | NotRun |
| TF-CNF-05 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-CNF-06 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-CNF-07 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-CNF-08 | offline-real-services | Failed | task.status, interaction.confirmation, task.status, funds.S.calls, funds.S.outflow, funds.S.balance, funds.S.receipt, funds.S.bank_truth | Blocked | NotRun |
| TF-CNF-09 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-CNF-10 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-CNF-11 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-CNF-12 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-CNF-13 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-CNF-14 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-CNF-15 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-CNF-16 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-CNF-18 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-CNF-19 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-CNF-20 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-BNK-01 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-BNK-02 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-BNK-03 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-BNK-04 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-BNK-05 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-BNK-06 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-BNK-07 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-BNK-08 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-BNK-09 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-BNK-10 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-BNK-11 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-BNK-12 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-BNK-13 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-BNK-14 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-BNK-15 | offline-real-services | Failed | task.status, bank.failure_source | Blocked | NotRun |
| TF-BNK-16 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-BNK-17 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-BNK-18 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-BNK-19 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-BNK-20 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-VFY-01 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-VFY-03 | offline-real-services | Failed | task.status, task.status | Blocked | NotRun |
| TF-VFY-04 | offline-real-services | Failed | task.status, task.status | Blocked | NotRun |
| TF-VFY-05 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-VFY-06 | offline-real-services | Error | ValueError | Blocked | NotRun |
| TF-VFY-07 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-VFY-08 | offline-real-services | Failed | task.status | Blocked | NotRun |
| TF-VFY-09 | offline-real-services | Failed | task.status | Blocked | NotRun |
| TF-VFY-10 | offline-real-services | Failed | task.status, task.status | Blocked | NotRun |
| TF-VFY-11 | offline-real-services | Failed | task.status, task.status | Blocked | NotRun |
| TF-VFY-12 | offline-real-services | Failed | task.status | Blocked | NotRun |
| TF-VFY-13 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-VFY-14 | offline-real-services | Failed | task.status, funds.S.calls, funds.S.outflow, funds.S.balance, funds.S.receipt, funds.S.bank_truth | Blocked | NotRun |
| TF-VFY-15 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-VFY-16 | offline-real-services | Blocked | Ringo: 真实来源与绕过攻击语料尚未提供；不以自编block替代检测证据 | Blocked | NotRun |
| TF-VFY-17 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-VFY-18 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-VFY-19 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-VFY-20 | offline-real-services | Error | KeyError | Blocked | NotRun |
| TF-VFY-21 | offline-real-services | Failed | task.status, task.status | Blocked | NotRun |
| TF-VFY-22 | offline-real-services | Failed | verification.only_face | Blocked | NotRun |
| TF-VFY-23 | offline-real-services | Failed | verification.face_preserved, task.status, funds.S.calls, funds.S.outflow, funds.S.balance, funds.S.receipt, funds.S.bank_truth | Blocked | NotRun |
| TF-VFY-24 | offline-real-services | Failed | task.status | Blocked | NotRun |
| TF-QRY-01 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-QRY-02 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-QRY-03 | offline-real-services | Failed | fixture.processing_required | Blocked | NotRun |
| TF-QRY-04 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-QRY-05 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-QRY-06 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-QRY-07 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-QRY-08 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-QRY-09 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-QRY-10 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-QRY-11 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-QRY-12 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-QRY-14 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-QRY-15 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-QRY-16 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-RCV-01 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-RCV-02 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-RCV-03 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-RCV-04 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-RCV-05 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-RCV-06 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-RCV-07 | offline-real-services | Failed | fixture.processing_required | Blocked | NotRun |
| TF-RCV-08 | offline-real-services | Failed | concurrency.responses_equal | Blocked | NotRun |
| TF-RCV-09 | offline-real-services | Error | CookieConflict | Blocked | NotRun |
| TF-RCV-10 | offline-real-services | Error | CookieConflict | Blocked | NotRun |
| TF-RCV-11 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-RCV-12 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-RCV-13 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-RCV-14 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-RCV-15 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-RCV-16 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-RCV-17 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-RCV-18 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-RCV-19 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-RCV-20 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-RCV-21 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-RCV-22 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-RCV-23 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-OBS-01 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-OBS-02 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-OBS-03 | offline-real-services | Blocked | frontend/负责人: 需真实React事件/响应故障接缝及浏览器证据；接口快照不能替代页面验收 | Blocked | NotRun |
| TF-OBS-04 | offline-real-services | Blocked | frontend/负责人: 需真实React事件/响应故障接缝及浏览器证据；接口快照不能替代页面验收 | Blocked | NotRun |
| TF-OBS-05 | offline-real-services | Blocked | frontend/负责人: 需真实React事件/响应故障接缝及浏览器证据；接口快照不能替代页面验收 | Blocked | NotRun |
| TF-OBS-06 | offline-real-services | Blocked | frontend/负责人: 需真实React事件/响应故障接缝及浏览器证据；接口快照不能替代页面验收 | Blocked | NotRun |
| TF-OBS-07 | offline-real-services | Blocked | frontend/负责人: 需真实React事件/响应故障接缝及浏览器证据；接口快照不能替代页面验收 | Blocked | NotRun |
| TF-OBS-08 | offline-real-services | Failed | F36.search.empty | Blocked | NotRun |
| TF-OBS-09 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-OBS-10 | offline-real-services | Failed | task.status | Blocked | NotRun |
| TF-OBS-11 | offline-real-services | Failed | audit.admin_allowed, audit.linked_kinds | Blocked | NotRun |
| TF-OBS-12 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-OBS-13 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-OBS-14 | offline-real-services | Failed | audit.admin_allowed, audit.linked_kinds | Blocked | NotRun |
| TF-OBS-15 | offline-real-services | Failed | task.status | Blocked | NotRun |
| TF-OBS-16 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-OBS-17 | offline-real-services | Passed |  | Blocked | NotRun |
| TF-OBS-18 | offline-real-services | Passed |  | Blocked | NotRun |

每次运行生成独立目录；保留首次失败，复跑不会覆盖旧报告。逐步骤、实际模型proposal、确认/任务/银行/账本和断言证据见同目录report.json。

替身：离线固定proposal、按动作绑定的受控风险事实、指定读取/传输/日志中断及可控时钟。真实银行业务规则始终来自MockBankService。完整号码使用F36。

平台回归：[]
