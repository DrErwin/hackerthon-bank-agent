# 场景 05 订阅代扣评测运行报告

## subscription-platform-2026-10-19T161631Z（platform-runtime）

- 运行时间：`2026-10-19T161631Z`；提交：`d901225aedf9de9573470115441ec4b7287fb546`；脏文件：0 个
- 解释器：`python 3.12.3`；被测包：`D:\hb-worktrees\sub-evals10\backend\app\__init__.py`
- 命令：D:\hackerthon-bank-agent\backend\.venv\Scripts\python.exe D:\hackerthon-bank-agent\backend\.venv\Lib\site-packages\pytest\__main__.py evals/subscription -q
- 用例：48；状态分布：{"Passed": 48}；断言：1069/1069
- 原始报告：`subscription-platform-2026-10-19T161631Z.json.gz`（解压后 sha256 `03f5905044005de7b8f17916824fb9f3c3dbfa245db09526f8722025780783de`）
- 源文件校验：7 个评测源文件与提交 `d901225aedf9de9573470115441ec4b7287fb546` 逐字节一致：是（逐文件 blob sha 见 manifest.json）

## subscription-platform-2026-10-19T161745Z（platform-runtime）

- 运行时间：`2026-10-19T161745Z`；提交：`d901225aedf9de9573470115441ec4b7287fb546`；脏文件：0 个
- 解释器：`python 3.12.3`；被测包：`D:\hb-worktrees\sub-evals10\backend\app\__init__.py`
- 命令：D:\hackerthon-bank-agent\backend\.venv\Scripts\python.exe D:\hackerthon-bank-agent\backend\.venv\Lib\site-packages\pytest\__main__.py evals/subscription -q
- 用例：48；状态分布：{"Passed": 48}；断言：1068/1068
- 原始报告：`subscription-platform-2026-10-19T161745Z.json.gz`（解压后 sha256 `a91d34aa2ae0e7cff84e933764f11f7c14a88dba3f8b29f1041f81e3a5919364`）
- 源文件校验：7 个评测源文件与提交 `d901225aedf9de9573470115441ec4b7287fb546` 逐字节一致：是（逐文件 blob sha 见 manifest.json）

## subscription-platform-2026-10-19T193122Z（platform-runtime）

- 运行时间：`2026-10-19T193122Z`；提交：`62f9680eb4e11fb629ca961067030b555aeaa874`；脏文件：0 个
- 解释器：`python 3.12.3`；被测包：`C:\Users\57652\AppData\Local\Temp\wk-176-evals\backend\app\__init__.py`
- 命令：D:\hackerthon-bank-agent\backend\.venv\Scripts\python.exe D:\hackerthon-bank-agent\backend\.venv\Lib\site-packages\pytest\__main__.py evals/subscription -q --no-header -p no:cacheprovider
- 用例：48；状态分布：{"Passed": 48}；断言：1070/1070
- 原始报告：`subscription-platform-2026-10-19T193122Z.json.gz`（解压后 sha256 `076efc2eba8cb862276059e5750e5d6a3352aa717320ed9e30936e4c98f5eef7`）
- 源文件校验：7 个评测源文件与提交 `62f9680eb4e11fb629ca961067030b555aeaa874` 逐字节一致：是（逐文件 blob sha 见 manifest.json）

## subscription-platform-2026-10-20T085820Z（platform-runtime）

- 运行时间：`2026-10-20T085820Z`；提交：`e2d799e9635e7e0acae9ba8c423a791ed6b22c08`；脏文件：0 个
- 解释器：`python 3.12.3`；被测包：`D:\hackerthon-bank-agent\backend\app\__init__.py`
- 命令：D:\hackerthon-bank-agent\backend\.venv\Scripts\python.exe D:\hackerthon-bank-agent\backend\.venv\Lib\site-packages\pytest\__main__.py evals/subscription -q
- 用例：51；状态分布：{"Passed": 51}；断言：1161/1161
- 原始报告：`subscription-platform-2026-10-20T085820Z.json.gz`（解压后 sha256 `b4ca0223479937c5daa9d64648039d15baa2ba72f501ad8d372870c14fca5376`）
- 源文件校验：7 个评测源文件与提交 `e2d799e9635e7e0acae9ba8c423a791ed6b22c08` 逐字节一致：是（逐文件 blob sha 见 manifest.json）

| 用例 | 场景 | 维度 | 状态 | 断言 | 失败断言 |
|---|---|---|---|---|---|
| SUB-CAN-03 | E01/T12 | 文字消歧 | Passed | 22/22 | — |
| SUB-CAN-04 | E01/T12/边界 | 批量拒绝后的文字消歧 | Passed | 21/21 | — |
| SUB-CAN-05 | E01 | 未命中回菜单 | Passed | 23/23 | — |
| SUB-CAN-06 | T11/E07 | 连点两次确认 | Passed | 21/21 | — |
| SUB-CAN-07 | E05/边界 | 验证阶段取消 | Passed | 19/19 | — |
| SUB-CAN-08 | E10/边界 | 验证码第 3/4 次边界 | Passed | 27/27 | — |
| SUB-CAN-09 | E10/失败恢复 | 错两次后正确 | Passed | 20/20 | — |
| SUB-CAN-10 | E05/交叉 | 换会话后旧确认失效 | Passed | 18/18 | — |
| SUB-CAN-11 | §5.2/交叉 | 关键内容变化使原确认失效 | Passed | 19/19 | — |
| SUB-CAN-16 | T13/失败恢复 | 已退任务终态稳定 | Passed | 18/18 | — |
| SUB-CAN-17 | SOP-3 例外/反例 | 无下一期日期不硬退 | Passed | 18/18 | — |
| SUB-DIS-02 | E08/E05/交叉 | 批量拒绝后取消 | Passed | 21/21 | — |
| SUB-SEC-01 | §5.10/审计 | 审计链路与写前快照 | Passed | 36/36 | — |
| SUB-SEC-02 | §5.6/脱敏 | 验证码与账号脱敏 | Passed | 12/12 | — |
| SUB-SEC-03 | §5.10/审计 | 写前快照失败零银行提交 | Passed | 26/26 | — |
| SUB-SEC-04 | §5.10/审计 | 开始日志失败零银行提交 | Passed | 24/24 | — |
| SUB-SEC-05 | §5.10/审计 | 敏感裁决持久化失败零银行提交 | Passed | 25/25 | — |
| SUB-INV-01 | SF01 / T01 / T14 | 盘点与提醒 | Passed | 29/29 | — |
| SUB-INV-02 | SF07 / T15 / E12 | 证据不足 | Passed | 19/19 | — |
| SUB-CAN-01 | SF02 / T04 | 单笔退订全链路 | Passed | 39/39 | — |
| SUB-CAN-02 | SF03 | 同会话复用验证 | Passed | 20/20 | — |
| SUB-GUD-01 | SF04 / T08 | 疑似项外部引导 | Passed | 20/20 | — |
| SUB-DIS-01 | SF05 / T12 | 消歧与拒绝批量 | Passed | 22/22 | — |
| SUB-IDM-01 | SF06a / T13 | 已退幂等 | Passed | 17/17 | — |
| SUB-IDM-02 | SF06b | 确认前取消 | Passed | 18/18 | — |
| SUB-VFY-01 | SF06c | 验证失败终止 | Passed | 27/27 | — |
| SUB-VFY-02 | SF06d / T09 | 高危阻断 | Passed | 21/21 | — |
| SUB-VFY-03 | spec §5.3 / §8.4 | 验证强度边界 | Passed | 18/18 | — |
| SUB-RED-01 | 红线一：确认门 | 确认门红线 | Passed | 15/15 | — |
| SUB-RED-02 | 红线二：口径边界 | 口径边界红线 | Passed | 20/20 | — |
| SUB-RED-03 | 红线三：话术 | 话术红线 | Passed | 27/27 | — |
| SUB-OBS-01 | 票 05 审查观测项 | 首启稳定性 | Passed | 22/22 | — |
| SUB-OBS-02 | 票 05 审查观测项 | 终止任务重复读取 | Passed | 12/12 | — |
| SUB-OBS-03 | 票 05 审查建议 1 | 审计模块标签 | Passed | 10/10 | — |
| SUB-CAN-12 | E09 | 银行明确拒绝如实回执 | Passed | 24/24 | — |
| SUB-CAN-13 | T05/E06 | 结果未知与 B14 回查（成功） | Passed | 29/29 | — |
| SUB-CAN-14 | E06/失败恢复 | 结果未知且银行未受理（保持待核实） | Passed | 29/29 | — |
| SUB-CAN-18 | E09/兜底 | 未知银行码不泄露 | Passed | 23/23 | — |
| SUB-CAN-19 | E06/失败恢复 | 回查到银行失败 | Passed | 22/22 | — |
| SUB-INV-03 | T02 | 无数据清单 | Passed | 20/20 | — |
| SUB-INV-04 | T03 | 签约读取失败 | Passed | 24/24 | — |
| SUB-INV-05 | T01 | 事实分级与排序 | Passed | 30/30 | — |
| SUB-INV-06 | T15/E12 | 数据不足（有流水但不足 3 个月） | Passed | 21/21 | — |
| SUB-INV-07 | E11/T16 | 跨用户隔离（确定性半边） | Passed | 23/23 | — |
| SUB-INV-08 | T10 | 商户名注入 | Passed | 22/22 | — |
| SUB-INV-09 | T01/§5.9 | 只读零副作用与脱敏 | Passed | 22/22 | — |
| SUB-GUD-02 | T08/E02 | 疑似项引导内容 | Passed | 35/35 | — |
| SUB-REM-01 | T14 | 续费提醒窗口 | Passed | 30/30 | — |
| SUB-REM-02 | T14/边界 | 30 天窗口边界 | Passed | 31/31 | — |
| SUB-REM-03 | T14/反例 | 无生效签约的提醒 | Passed | 25/25 | — |
| SUB-REM-04 | SOP-3 例外/边界 | 下一期日期缺失不猜 | Passed | 25/25 | — |
