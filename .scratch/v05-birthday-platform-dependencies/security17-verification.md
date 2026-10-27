# 17：限定释放来源的局部验证

实施：[v05-birthday-platform-dependencies/17](issues/17-release-confirmation-origin.md)；来源：[Issue #340](https://github.com/DrErwin/hackerthon-bank-agent/issues/340)（转给Erwin，Assignee DrErwin）。基线main `f4a9872432cbfd9ba13902efc77f467084ede450`，实现固定head `087ceca1c58a6e217c9c1c224284470b5d3d7756`。

## 红绿与实际范围

- 接口未实现时，同一真实安全/银行Rig中，S1已批准并实际冻结，S2复用确认ID产生新version后，读取授权精确原版本失败：**1 failed / 1.09s**，AttributeError指向缺少get_release_confirmation。见[原红灯XML](evidence/2026-10-27-security17-red.xml)，SHA256 `91f14bc1815192eea19c6b37f167ffe97bc843dc0e2ca96382c33fa424884cee`；原Cross09的4 fail / 2 pass不改。
- 新增定向：**47 passed / 7.09s**，见[XML](evidence/2026-10-27-security17-local-final.xml)，SHA256 `0b8386401dcf04c62e59160a3de62fbdc9fc02a20e4961c12b3d42e6c6b5c605`。当前/历史位置分别测试错误ID/version、主体/session/op/action/revision、pending/条款、时间不合法；缺历史不能改取S2已批准的新版本。
- 安全目录：**574 passed / 64.22s**，见[XML](evidence/2026-10-27-security17-full.xml)。这是本目录集合，不沿用其他组合回归的计数。无旧测试/断言删除或改期望。

## 已观察的边界

冻结/原批准/授权均来自真实隔离Rig，模型0次。读取前后整个应用/银行表内容比对不变；S2当前待确认记录及S1历史原样保留，旧get/history仍拒绝foreign会话。原返回记录无法作为S2新grant，迟到S1原grant也不能把active记录改回pending；旧卡答复继续拒绝。

原S1会话和确认到期后，active/completed限定释放仍可读取批准当时的原来源，查询不写expired、不使原授权失效。两个连接的快照测试中，在读取授权后另一真实事务成功提交invalid与S2新卡；当前读取仍只返回首次快照中原批准，不把两次快照拼接，也不阻挡writer或撤回其写入。后续读取立即拒绝invalid。此只证明一致的历史读取，不能用一次读取代替执行前安全检查。

实现复用原get_release_authorization的主体逻辑，只提取为同连接私有查询。普通get_release_authorization行为保持；新入口才额外要求精确上下文ID、已生效冻结绑定与严格原记录。没有数据库schema或公开契约字段变化，不复制银行余额/限额/释放金额规则。

平台16尚待消费公开方法并回放真实Cross09六阶段；本票不修改平台/Cross生产，不称联合绿、真实模型/HTTP页面验收或本人安全接受，不重跑01–03模型批，也不写比赛材料。
