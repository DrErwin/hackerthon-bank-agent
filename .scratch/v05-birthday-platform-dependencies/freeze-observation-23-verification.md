# 平台23：只读冻结提交观察验证

日期：2026-10-27。来源问题 [Issue #352](https://github.com/DrErwin/hackerthon-bank-agent/issues/352)，转给Erwin / Assignee DrErwin。生产仅 `backend/app/agent_platform/birthday_runtime.py` 增加公开观察方法；README解释能力。Cross Protocol/消费、安全和银行代码未修改。

## 固定源码与实际组合

最新受测源码 `62eca24aaa30d2891058163f44ae42f2d36f7de6`，base main `5278f870a0b3da09b0fc404ccf15abd3d1f74998`（含API22及P01接线）。生日运行源blob `e8b3b35e7e3667f4463173687d6985039ff3dbed`，backend树 `ea7036499e94d65849242e6c1c01194e731e2d3c`。

```text
python -m pytest backend/app/agent_platform/test_birthday_freeze_observation.py backend/app/agent_platform/test_birthday_runtime_wiring.py -q --basetemp=../pytest-platform23-main --junitxml=.scratch/v05-birthday-platform-dependencies/evidence/2026-10-27-platform23-main.xml
```

`PYTHONPATH` 指向本工作树backend，使用本机既有backend解释器。真实Harness、确认/验证码/模拟人脸、安全状态与MockBank；模型为明确NoopModel，未调用真实模型。新增观察31项与既有生日装配5项，同一批 **36 passed / 0 failed/skipped / 76.24s / exit 0**，[原始JUnit](evidence/2026-10-27-platform23-main.xml)。

先前基线ef8f9220的同36项为76.92s。同步5278f870时仅README新增段落位置冲突，保留双方说明；运行文件/新测试未冲突，但主线Harness/风险来源有变化，故重新验证这36项。不是另跑全backend，也不把两批累加为72个唯一用例。

## 三态与只读边界

- 当前owned task及既有owner/round/session门先执行；ACCESS_DENIED及STALE_ROUND仍拒绝。只认当前freeze动作的准确op、正整数revision及相同plan参数，历史退休号unknown，不默认revision、不伪装S1。
- 只有银行原号Found、准确bank.freeze_funds且terminal才submitted；即使已有completed claim，银行NotFound或读取不确定仍unknown。
- 无claim、真实OperationNotFound、公开gateway已排空，随后再读claim仍无并复核动作来源未变，才not_submitted。真实在途、processing/unknown claim、银行None/异常/processing与来源漂移均unknown。
- 直接构造不带确认、验证或释放授权的只读ExecutionSecurityContext；不使用会复用验证和写绑定/审计的通用runtime._context。
- 探针期间拦截银行四写、claim_execution、验证复用及ports的gate/execute/requery/grant/bind/finalize；断言这些入口零调用且任务快照、已有claim与银行操作不变。并发claim/动作漂移为明确故障注入，注入自身的改变单列核对；真实银行在途使用已批准/验证的原冻结，释放线程后只完成原有一次写。
- 退休旧号测试借既有平台provider检查点准备S2，缓存Cross消费为明示故障替身；该测试不是Cross09新消费闭环。

## 原失败与重叠范围

缺少公开方法时1 failed/7.98s，[原红](evidence/2026-10-27-platform23-before.xml.gz)。第一版16项为15过/1失败：错轮STALE_ROUND被误吞，[中间原红](evidence/2026-10-27-platform23-first.xml.gz)保留；已恢复原拒绝并消除通用上下文的验证复用副作用。随后28项通过，再补三项来源不确定检查形成最终31新项。

两份红XML含原始trace行尾，采用无损gzip保存；解压逐字比较与原始XML一致，未清理或改写失败内容。原XML本机副本保留在忽略目录 `.mnemon/platform23-original-xml/`；各批[原始字节SHA256与计数](evidence/2026-10-27-platform23-hashes.json)独立记录。28、36及最新36批互有重复，不相加成新增用例。

## 后续

该只读观察不是关闭hold或执行资金的授权；Cross须在既有Harness任务串行锁内消费，再沿原号requery/bind与原限定finalize。Cross09的原14117/c79f红未在本票修改，真实新冻结取消释放500元、未知保hold由09独立验收。根代理最终全backend、真实模型/HTTP页面、截图与真人安全接受仍分别推进。作者仅交独立PR两轴，不自合并或关闭整体问题。
