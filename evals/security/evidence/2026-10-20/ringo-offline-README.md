# Ringo 离线组合证据，2026-10-20

本目录本轮新增18份gzip正本，文件统一以前缀2026-10-20-ringo命名。完整文件名、解压后JSON的SHA256及压缩文件SHA256见[索引](2026-10-20-ringo-offline-index.json)。既有10-20导出补充报告保持原样。

后补当前主线整理的2份正本，合计20份：[重基补充索引](2026-10-20-ringo-rebase-supplement-index.json)记录#164候选206 Passed、#169安全实现目录292 Passed。提供方基线7a8dd1e，保留PM已合的L03，分别为独立冻结分支0b8b2bad及其风险增量dc9db051。这两份与357行的8329dbec组合分别统计，未代替原报告。

## 结果

| 报告后缀 | 结果或用途 |
|---|---|
| current-composite-catalog | 138主用例/295参数/357行，20 Passed / 12 Failed / 325 Blocked |
| current-composite-security | 136 Passed，仅评测代码测试 |
| current-composite-backend | 1041 Passed / 1 Failed，待查#186 |
| backend-isolated-retests | 相同失败节点两次隔离均Passed，保留全量失败 |
| current-detector-terminal | 核心12 Passed及合法对照Passed；提示观察导致整例12 Failed，#173 |
| export20-merged | 20项专项Passed，非整例验收 |
| independent-l03-76 | 主线策略加L03唯一改动，76 Passed；远端分支55cf1b5 |
| provider-fixes-retest / merged-audit-minimum | #174两种故障与#145审计局部实测满足；相应SEC整例仍Blocked |
| function-readiness | 12个功能族设计与逐条映射，29个验收条目数量不足，完整数量门未通过 |
| source-snapshot | 提供方15份变更源码blob匹配8329dbec，147个代码/数据文件SHA256，未称纯main |

historical前缀保存40a61c3组合的失败事实，candidate保存b3a00b0审计候选复验。历史目录报告含一次L009子进程120秒超时，audit-authorisation-retest取得局部组件观察，最新全目录已无该失败。

当前全目录JSON SHA256：`8BC453C719D56641A6C5A1F4F0DC8B4B3D27D9924675EA7C0C66F55027651F05`。

当前安全测试JSON SHA256：`CB2D84E0B1651FEDC77DDED77BAEEB1E4B9669B3E354B31D2A194157EF024778`。

当前后端JSON SHA256：`656B827F3D5239F1789301430881F2B5FBF6E312C4DCCA05386F9A117A76D5C2`。

## 复现边界

来源主线8329dbec，QA组合包括待合#165/#169及评测增量。运行报告保存实际本地提交，报告入口和数据哈希见source-snapshot。L03独立切片另用主线策略版本v04-local-demo-read-report-2；完整组合沿用原待合风险策略版本，二者分别验证。

七份来源文件blob均与冻结清单一致；本地Git缺历史来源提交，故all_blob_hashes_verified=false、all_working_copy_hashes_match=true。历史提交对象溯源与本地内容一致性分别记录。

模型调用0。本批没有页面自动取证；自然语言理解、间接注入入口、缺失的管理及记忆公开接口按readiness保留缺口。银行资金副作用按真实SQLite账户、操作及账本核对。报告已排除原始验证码、秘密和组件参数；节点标识使用哈希，#186具体失败断言未留存并明确为证据限制。
