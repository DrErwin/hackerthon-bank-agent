# 场景 05 订阅代扣评测运行报告

## subscription-platform-2026-10-19T081554Z（platform-runtime）

- 运行时间：`2026-10-19T081554Z`；提交：`654a0e845b971487f753e39ff70a9ab4301fef4c`；脏文件：3 个
- 解释器：`python 3.12.3`；被测包：`D:\hb-worktrees\sub-evals\backend\app\__init__.py`
- 命令：D:\hackerthon-bank-agent\backend\.venv\Scripts\python.exe D:\hackerthon-bank-agent\backend\.venv\Lib\site-packages\pytest\__main__.py evals/subscription -q --no-header
- 用例：17；状态分布：{"Passed": 17}；断言：349/349
- 原始报告：`subscription-platform-2026-10-19T081554Z.json.gz`（解压后 sha256 `1f485509bbec2c9eb61ce7114c44cd07e2f526176643984cd65f3ae0f1f1a8a2`）

| 用例 | 场景 | 维度 | 状态 | 断言 | 失败断言 |
|---|---|---|---|---|---|
| SUB-INV-01 | SF01 / T01 / T14 | 盘点与提醒 | Passed | 29/29 | — |
| SUB-INV-02 | SF07 / T15 / E12 | 证据不足 | Passed | 19/19 | — |
| SUB-CAN-01 | SF02 / T04 | 单笔退订全链路 | Passed | 39/39 | — |
| SUB-CAN-02 | SF03 | 同会话复用验证 | Passed | 20/20 | — |
| SUB-GUD-01 | SF04 / T08 | 疑似项外部引导 | Passed | 19/19 | — |
| SUB-DIS-01 | SF05 / T12 | 消歧与拒绝批量 | Passed | 22/22 | — |
| SUB-IDM-01 | SF06a / T13 | 已退幂等 | Passed | 17/17 | — |
| SUB-IDM-02 | SF06b | 确认前取消 | Passed | 18/18 | — |
| SUB-VFY-01 | SF06c | 验证失败终止 | Passed | 27/27 | — |
| SUB-VFY-02 | SF06d / T09 | 高危阻断 | Passed | 21/21 | — |
| SUB-VFY-03 | spec §5.3 / §8.4 | 验证强度边界 | Passed | 18/18 | — |
| SUB-RED-01 | 红线一：确认门 | 确认门红线 | Passed | 15/15 | — |
| SUB-RED-02 | 红线二：口径边界 | 口径边界红线 | Passed | 20/20 | — |
| SUB-RED-03 | 红线三：话术 | 话术红线 | Passed | 21/21 | — |
| SUB-OBS-01 | 票 05 审查观测项 | 首启稳定性 | Passed | 22/22 | — |
| SUB-OBS-02 | 票 05 审查观测项 | 终止任务重复读取 | Passed | 12/12 | — |
| SUB-OBS-03 | 票 05 审查建议 1 | 审计模块标签 | Passed | 10/10 | — |
