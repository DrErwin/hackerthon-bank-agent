# v05-cross-chat-resume/01 验证与消费接缝

基线 `17f7ef2c2f2021c866ca4e1f1ce7757d31bace0b`。受测最终源码
`13469e6d24d6a3e57d0b38cc3fb3f45106d6bf18`，backend树
`7aa78881cccb48d51c348a170a8247c60b2378c2`，agent_platform树
`597365c5057ece6f44b346c1a926308da9b76d3f`。生产model.py/harness.py与
`c8d476efd5c8511f85afc02dd4191bc09b09feb2`字节相同，后续只补本组scratch。

## 红绿与范围

- 原17f确定性红例 **1 failed /5.78s**：实际planner工具不接受resume，Harness
  返回失败而非原任务建议。原XML无损压缩保留在provider-before.xml.gz。
- 最小生产修补 **1 passed /4.48s**：只提出原task/revision的无字段resume，
  六个银行写入口调用数零，原任务不改、不创建新任务。
- guard首次扩大 **121 passed /3 failed，32.18s**。三个失败是测试未先创建匹配
  owner/session/round会话导致FK错误，尚未到产品边界；无损归档
  provider-guard-fixture-before.xml.gz，不当产品失败或通过。
- 修正真实会话夹具后单批 **124 passed /32.23s，0 failed/error/skipped**。
  本票25项及原续办、上下文、模型规划/协议、Harness五文件99项；无重复节点。

最终命令：

```text
python -m pytest backend/app/agent_platform/test_chat_resume.py backend/app/agent_platform/test_continuation_planning.py backend/app/agent_platform/test_planning_context.py backend/app/agent_platform/test_model_planning.py backend/app/agent_platform/test_model_protocol_failure.py backend/app/agent_platform/test_harness.py -q --basetemp=../pytest-chat-resume-provider-final --junitxml=.scratch/v05-cross-chat-resume/evidence/2026-10-29-provider-final.xml
```

Python为D盘既有venv，PYTHONPATH显式指本树backend；子进程清除BANK_LOCAL_CONFIG
与BANK_PENSION_DEMO_PROFILE，所有数据库为独立pytest目录，模型均明确替身。
实际未运行模型/银行/浏览器不受影响；本票不声称真实页面回验通过。

Spec独立固定13469e6d结论0must，另两文件57 passed/14.28s由独立代理回报；57是
作者124的重叠范围，不相加。Standards、精确CI、合入及真人接受由根任务分别核对。

## 固定消费者合同

ContinueProposal的action新增resume，仅task_id/task_revision，其余payload字段
必须None或省略；包括空text/选项也拒绝。只建议当前唯一未完成、可信同域、同版本、
allowed含resume、running且无交互卡的任务；recovery_required不借resume放行。
模型提示说明继续核实原进度不构成确认/验证/授权；无关键词直接执行路径。

API消费者另票须显式映射 `response={"choice":"resume"}`，沿原请求UUID和现有
continue_task(..., publish=False)，不设recover_session、不落到query。消费者继续
核同线程、身份、版本与allowed；底座与消费必须分别交付后才可回验普通聊天闭环。

所有原红、夹具准备失败、最终JUnit及SHA摘要保留；不修改根51真实页面红或原银行。
