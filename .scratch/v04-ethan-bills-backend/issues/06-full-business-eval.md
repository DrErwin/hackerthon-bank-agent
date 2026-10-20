# 06：完整账单业务自动化与证据

Ticket ID: v04-ethan-bills-backend/06
Type: 评测
Owner: 周恩宇
Directory: evals/bills/
Status: in_progress（17 条 L01 公共真实链路当前主线重跑已通过，PR #198 阶段一待合；全功能/异常下限尚未达标）
Package: [v04-bills/01](../../v04-bills/packages/01-bills-backend.md)
Spec: [本人规格](../spec.md)
Core scenarios: [BF01—BF06](../../v04-bills/spec.md)
Blocked by: 核心 L01/L02/L03 模块均已合并；后续本票仍需为 L02、L03 和其余错误类型补场景满足每子功能≥10/每类异常≥3；真实 L02 准入依赖 #188/#187/#190 联调；真人专业验收不由本票代签。
Verification: 冻结规则逐项映射；每功能>=10、每类异常>=3并消除缺口；Passed/Failed/Blocked分别报告，原始JSON.gz/sha256归档。

## 验收

测试调用真实公开业务能力与银行接缝，不只调用私有计算器；不以stub/skip/xfailed制造全绿。专业检测与业务响应分层记录，不代Ringo签核。

## Comments

- 2026-10-19：启动就绪 L01 公共路径的首批评测，使用独立 `evals/bills/` 分支，运行及归档见下列实证。本票按“逐路径就绪即验证”推进；L02/L03 及其他路径分别记录依赖，不声称本票的数量门槛或联合验收已通过。

### 2026-10-19：第一阶段 14 个公共 L01 场景已实施与实跑

- 本地受审源码 `89c0fbf5fccab3430853afdcc21899c7c4b2b0a8`，最终公开源码 [7439ced9136984f9f4be27342b6adb0c7726cc14](https://github.com/DrErwin/hackerthon-bank-agent/commit/7439ced9136984f9f4be27342b6adb0c7726cc14)；两者 Git 树均为 `e76c814a24bf4e30da15eaadc88e1fd0cd753d18`，已核对相等。相对本票基线 cac529389e25f5eacfed3bc3f32dbe1786cfb67c 只改 evals/bills 的 README、用例 JSON/Markdown、公共业务测试和运行器 5 个文件。
- `BILL-PUBLIC-01`—`14` 经真实注册 L01、Harness、SQLite checkpoint、SecurityGate、执行器、BankGateway 与种子 Mock Bank 运行，覆盖本人多/单账户、范围澄清、餐饮明细及跨月退款、消费/转账/利息分离、完整空集、银行范围拒绝、安全门拒绝、B01/B08 重试、部分账户失败、防重、取消和跨会话续办。
- 实际 `python -m pytest -q evals/bills/` 为 **64 passed**，含本阶段 **14 项公共场景**与既有 **50 项黄金/工具测试**。14 是运行场景，不与既有 96 条设计或 147 项算术/工具相加为独立覆盖；Harness 防重也不替代 /09 的模块 M2 验证。
- 每个场景核对真实银行库全部表摘要、余额和资金提交次数不变；金额独立按实际 B08 求和，明细逐字段对照银行及退款原单。规划器、授权/LOW 风险策略是明确替身，09/10/11 注入具名 CALL_TIMEOUT；因此只认定业务对相应结果的响应，不代签生产策略或攻击检测。
- 独立 Spec / Standards 已复核。运行器要求 40 位精确提交，执行前后核对完整源码 Git blob、真实包初始化器及 app 导入路径；缺样本、错误、skip 或缺银行不变证据不能得到 Passed。独立静态来源检查确认 115 份源码匹配；正式执行的模块导入清单、逐样本记录、原始 gzip 与 SHA256 见下节 runner 归档。
- 本阶段 `overall_status=partial`，原受测版本的 7 条 L02/L03/导出/模型/页面/专业安全路径依赖单列，不送入 pytest 当 skip 或通过；这是该次 L01 运行的边界，不作为全项目当前状态。L01 自身尚缺非正净额、比较、精确边界和更多错误样本等，明列 `remaining_coverage`，不假借外部依赖。每子功能 ≥10、每类异常 ≥3 的整票门槛仍需继续补齐。

### 2026-10-19 16:41：正式 runner 与原始报告已归档

- 实际命令 `python evals/bills/run_business_evidence.py --revision 7439ced9136984f9f4be27342b6adb0c7726cc14`，先发布真实源码再执行。开始 `2026-10-19T08:41:46.267213+00:00`，结束 `2026-10-19T08:41:50.875779+00:00`；银行业务时钟另为 `2026-10-14T13:00:00+08:00`。
- **14 collected / 14 passed / 0 failed / 0 skipped / 0 errors / 0 collection errors**，pytest 实际输出 **14 passed in 3.75s**。正式报告模式 `git_object_verified_complete_business_sources`，115 份源码/种子与 44 个实际应用模块导入核对通过；27 条公共响应观测、14 份真实银行全部表摘要/余额不变及零资金提交证明齐全。
- 原始文件 `evals/bills/evidence/2026-10-19/20261019T084150880617Z-python3.12.14-public-l01-phase1-7439ced91369.json.gz`；解压 JSON SHA256 **`af6f959b06cbcc1a7518c08540a2e3eb25e3f2e6edbc90d92421e26b9ff31cd1`**，压缩 19705 字节、原始 90771 字节。原始 run_id `3525014c-09eb-421c-b46b-b4d79097f618`。
- 本地归档 `830900fe519d0f786ee3df5641730851b263af8f`，最终远端分支 `test/bills/public-business-evidence-06` 的 [6b77cc28c7af97a9a1028e7d68726f01b92daee6](https://github.com/DrErwin/hackerthon-bank-agent/commit/6b77cc28c7af97a9a1028e7d68726f01b92daee6) 已推送；树 `84f9daef8f63645feb5799b4bcfa469dfca21abf`，远端父提交就是实际受测源码 7439ced。归档只新增本报告并更新说明，不回写源码或旧报告。
- 独立归档复核逐一验证原 gzip 字节、解压 SHA256、115/115 源码指纹、44 个导入路径、14 个唯一样本及时间、27 次响应、14 份银行不变证明；旧 5 份证据逐字节未改。本轮实际最终业务状态是 **10 succeeded / 2 正确拒绝 failed / 1 waiting_input / 1 cancelled**，不能将“14 项断言 passed”写成“14 次业务请求成功”。
- 7 条原受测路径依赖和 `overall_status=partial` 保留；/07 已另启动可行 HTTP 报告/导出补证，该新进展不反向修改本原始报告。当前本人仍只有 PR #93、#151 两个未合 PR，本票先交付远端分支及可复核证据，未开第三个 PR，未关闭票06。

### 2026-10-19 16:59：补齐三项就绪缺口，17 场景新版实跑

- 在原 14 场景归档上增加 `BILL-PUBLIC-15`—`17`：真实退款原单的窄范围补查失败后沿原任务恢复；银行原范围非空但所选类别无匹配；排除普通类别时先澄清、任何读取前等待显式新口径。新增源码仍只改 `evals/bills/` 的 5 个文件，没有修改生产逻辑、原报告或 7 条受测路径依赖。
- 固定受审本地源码 `25d13701787db8fafb91c7cf8f6976edbe909981`，正式发布受测源码 [49ab58e21634371313cedc8488da77f25f09e95d](https://github.com/DrErwin/hackerthon-bank-agent/commit/49ab58e21634371313cedc8488da77f25f09e95d)；两者树均为 `47feaf95b286c8c089c30f583a08d8f80bfce939`。独立 Spec / Standards 增量复核均无未解决发现；错误注入明确扩为 09/10/11/15 四例，真实银行库不变及零资金提交断言沿用。
- 预检公共场景 **17 passed in 4.32s**，目录合跑 **67 passed in 3.91s**。随后对已发布源码执行正式命令 `python evals/bills/run_business_evidence.py --revision 49ab58e21634371313cedc8488da77f25f09e95d`，实际 **17 passed in 4.36s**；开始 `2026-10-19T08:59:21.194006+00:00`，结束 `2026-10-19T08:59:26.331989+00:00`，17 collected / 0 failed / 0 skipped / 0 errors / 0 collection errors。
- 正式报告 `evals/bills/evidence/2026-10-19/20261019T085926337455Z-python3.12.14-public-l01-phase1-49ab58e21634.json.gz`，解压 SHA256 **`28a3f25af3c9c50f1cc640acfe51da7ca7f8290905a19732a7723742c62fbe57`**；压缩 21374 字节、原始 103486 字节，run_id `43b13192-85c4-4bd6-a109-6a9ba5e73ea9`。本地归档 `3136bfa7972bf931765707ff8b06d047c03f214f`，树 `50f20da211ccd710a4ce6aa4e90a522d3cd24797`，父提交就是实际受测源码 49ab58e。
- 最终归档远端 [0c06511e9470102216e78df5b83f3dc79c2a5c82](https://github.com/DrErwin/hackerthon-bank-agent/commit/0c06511e9470102216e78df5b83f3dc79c2a5c82) 已推送到 `test/bills/public-business-evidence-06`，与本地归档同树、同实际受测源码父提交。根执行者再次逐一独立对照 115 份 Git 源码，归档保持可追溯。
- 115 份源码、44 个实际 app 模块、33 条公共响应与 17 份银行不变证明齐全；原 6 份证据字节未变。17 项断言全部 passed，最终业务状态为 **13 succeeded / 2 正确拒绝 failed / 1 waiting_input / 1 cancelled**。这是包含首批 14 的完整新版复跑，不能累计为 31 场景；67 项目录回归为既有 50 加本轮 17，也不与 147 项算术/工具合跑相加。
- 票 06 仍为 `in_progress` / `overall_status=partial`。每子功能 ≥10、每类异常 ≥3 的整体门槛、更多 L01 复杂范围/比较/边界及错误变体仍需补覆盖；这些是自有用例缺口。受测 L01 版本的 7 条路径依赖保留在原始报告，票 07 的另层 HTTP 结果单独认定。

### 2026-10-20 晚新主线实跑与 PR 提审

[PR #198](https://github.com/DrErwin/hackerthon-bank-agent/pull/198) 正式提交了只在 `evals/bills/` 的 17 条公共 L01 自动化。固定源码 `c2e8f3ea2949c32bf4526b426f647e6c03f69f5c` 在 [GitHub Actions #39425788637](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/39425788637) **17/17 passed、0 failed**，133份真实源文件核验、44个真实模块导入、17例资金不变检查；[原始 gzip 和 SHA256](https://github.com/DrErwin/hackerthon-bank-agent/blob/a13234205b79f54ab630da8ce66f35076e5a4ec1/evals/bills/run-log-public-06.md) 已上传。最新 PR head [CI #39426994398](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/39426994398) **967 backend +14 MockBank passed**。这是对当前合并基线的新实跑，不是复用历史证据。**仍为 phase1 partial**；BF01—BF07 与数量下限不能由 17 条直接推定全通过。
