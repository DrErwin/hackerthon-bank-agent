# v05-demo-reset-api/01 验证记录

2026-10-27。本票只修改 `backend/app/api/` 及本组过程材料。最终依赖组合的完整API回归已通过，Standards独立审查0必须项；Spec独立审查与最终合入另记。

## 实际运行

- 原代码新增首个F30 HTTP回归真实失败：期待管理员拒绝403，实际404（端点不存在），`1 failed`；不是人为固定成功。
- 第一轮7项API重置检查通过；连同既有 `app/api/test_app.py` 与平台业务时钟定向，**95 passed / 0 failed**，233.43秒。
- 最终11项API重置HTTP检查 **11 passed / 0 failed**，11.18秒：预览权限/只读/原号重放、等待确认任务可以重置、普通请求停收、原确认与参数冲突、旧轮授权拒绝、记忆预置、历史审计保留和本人只读范围、银行响应丢失恢复、记忆局部失败与管理重新登录、旧配置重启、真正超时网关future及API worker占锁、必要审计失败零银行重置。
- 受测组合 `07b6fc50`（消费平台时区修正 `62bc3372`）上，`app/api/test_demo_reset.py app/agent_platform/test_demo_runtime_clock.py` **14 passed / 0 failed**，19.37秒。[原始JUnit](reset-results.xml) SHA256 `C9E6FB6F4B9BC1B4E7FE3F6B165CFE9446C068A98E5505856F0A5BAE2339876C`。随后只将已具备的公开bank属性直接取值，最终依赖整合后还需API目录回归，不把旧组合当最新main全量。
- 补充正式 `local_demo` 装配：整体重置后以新轮新会话完成500元的真实有限安全策略、确认、验证码与模拟银行转账，**1 passed**，8.16秒；仅Chat connector输出为脚本替身。该用例使本票API新增用例共12项，验证新轮不会被最初config关闭；不是新真实模型/页面证据。

测试均使用新的临时SQLite。规划器与风险授权是明确测试装配；银行、账户、真实future、API HTTP、记忆与共享业务时钟使用本地正式实现。一个future探针为了只验证重置协调，显式注入允许该固定测试动作的网关授权；它不是专业安全或真实模型验收。

## 协调与断点事实

F31先用API专属事务绑定确认与原管理号并停收，再非阻塞尝试API锁；已有worker占锁立即返回同号 `running/waiting_inflight`。持锁时网关排空检查使用timeout=0，不关闭executor、不等worker finally，后台原工作可以结束。

银行、API用户会话授权、记忆预置、共享业务时钟分别推进；全部完成才提交外部新轮次与成功。原管理号、初始逻辑时间和阶段持久化。银行响应丢失后先查询原银行管理号，不再清空已进入新轮的银行事实；F32只读，不偷偷续做。跨阶段恢复由同一F31原请求推进。

旧应用任务和审计不删除；API旧用户授权失效、平台动态可信轮次与银行旧轮拒绝共同阻止旧按钮/确认/验证写新环境。管理身份保留原号查询；新管理员只读本人持久管理记录的source_round历史任务与事件，其他管理员或无记录的任意旧轮拒绝。旧轮导出权限不扩大。

## 依赖与未做

组合依赖为PR322银行管理、PR325排空/逻辑起点getter、PR326公共模型、平台票12公开runtime.bank与共享时钟。组合验证时依赖分别保留独立提交，最终PR只交API差异，不把上游代码算本票交付。F25/F29、前端管理页、浏览器真实操作、真实模型、共享演示库、账户支付和比赛材料不在本票；整体最终接受仍由主代理安排。

## 最终完整组合（2026-10-27）

主代理确认组合树后，只运行一次最终完整批次。基线 `origin/main@0b72b0a1c2ee7a95367a33f25d1a40eeea2cd880` 已含PR323/324/325/326；随后只取PR327自身5提交（原head `695ce6e5c26466bf16f2a4295a917ffac886945b`）、PR328自身6提交（原head `2a042e75a63d4a203c82515a12d15fbe35350fab`）与PR329自身4提交（原head `74815655799c4611999060b7489759cf97629548`）。临时组合 `704ba8967e8e5fa5654456cc0c77b69117ffe314` 的 `merge-base --is-ancestor origin/main HEAD` 退出0，源代码改动仅API与platform两目录。

受测树：backend `6973290d17add533fe81a80dc4f394e227c98d83`；API `e0952bf093706516b7b07d7a6ac22bb5ac080667`；platform `9d4d9670525eb99f2e28bbbf95d76d2729fc3ac4`，其中platform与PR328最终树完全一致。README唯一冲突保留原输入恢复与重置两节。运行期间未改源码，结束后复核以上树不变。

```powershell
python -m pytest app/api app/agent_platform/test_demo_runtime_clock.py -q --tb=short --junitxml=../.scratch/v05-demo-reset-api/full-api-final-results.xml -o junit_family=legacy
```

退出码 **0**，**251 passed / 0 failed / 0 error / 0 skipped**，532.49秒。其中API **246项**、平台时钟 **5项**；解析JUnit得到251个用例、251个唯一`classname + name`，无重复计数。[原始JUnit](full-api-final-results.xml) 45048字节，SHA256 `54DE3CDA7F621081D212BE5783F04B7B415C87B413AA92DA9E823B55D7FD1F8E`。最终交付分支机械重建后仍需核对API/platform受测树等价，不能仅凭相似提交名沿用结论。

此前两次未完成批次分别保留：一轮为纳入PR327审查修复主动中止，未得到完整JUnit，不能算通过；另一轮临时分支误用PR327旧父链而缺公共模型，收集阶段21个`collection failure`、未执行测试。[原始收集失败JUnit无损gzip](full-api-pr327-results.xml.gz) 解压后SHA256 `04F39D842E5FA8218F3198944168D4498505A4E4FBD3A9453042367E16514A10`（28593字节）。原始失败报告带CRLF与尾部空白，以gzip归档并逐字节验证解压等价，未为通过差异检查修改原文；压缩文件SHA256 `DB167D562CB1EAA588F0E25B914C681153075699F772CF81123BDFCB11003A5E`。此次从正确main重建后才运行上述最终批次，不将前两轮改写为产品测试通过或失败。

PR329原head `74815655` 的Repository checks因账户计费/额度问题未启动（run `40467827078`），不算CI通过或代码测试失败。上述证据仅为本地隔离库HTTP/平台/模拟银行工程验证，不替代真实模型、浏览器、真人安全签核或最终接受。

## 最终交付分支等价核对

在PR327/328/330合入后的 `main@e4f0fe503f0101920a2b1ae22545f2334ff89fea` 上，只重建本票原4提交与证据文档。API整棵树仍为 `e0952bf093706516b7b07d7a6ac22bb5ac080667`，与受测组合完全一致（含全部Python源与测试）；platform整棵树仍为 `9d4d9670525eb99f2e28bbbf95d76d2729fc3ac4`。两个目录的`git diff --quiet`退出均为0，main祖先核验退出0，README保留双方新增段落。机械重建不额外重跑。

主线PR330引入的security代码与其599项证据属于独立批次，未纳入本票251项旧组合；因此仅沿用上述API/platform受测树，不把新backend整棵树冒称为此次完整受测树。
