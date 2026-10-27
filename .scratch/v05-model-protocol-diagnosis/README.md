# 模型零工具回复：只读诊断

Status: diagnosed — 首选方案已由中控批准，生产实现另列 `v05-birthday-platform-dependencies/14`，本批不修改生产源码。

固定源码 `c7908dd6371e2a05ebe177f0fa86c2ffb93e14d9`，复用独立managed工作树的干净诊断分支。观察来源为中控给定的外部 `B-12-detector-20261027-01.json`，原文件SHA256 `e8b27e19f75398e02dc64436c75e5af6347296305e1227c07ef241f8f5adbeca`；诊断前后相等。本目录仅记录结构、hash和固定程序提示，不复制用户输入或模型自由回复。

## 根因与恢复边界

- 三个失败：`SEC-T-003/v01 r1`、`SEC-T-003/v02 r1`、`SEC-T-004/v01 r1`。provider HTTP200，assistant回复分别317/254/264字符、tool_calls均0；应用受理为HTTP202。原银行提交与operation均0，未观察到资金gate裁决。详见[不含自由文本的元数据](observation-metadata.json)。原B为12数据行+2控制、14次真实模型调用；本诊断真实模型调用0。
- [model.py:278](../../backend/app/agent_platform/model.py#L278)严格要求只有一个受控outcome，0个会抛`PlanningError(MODEL_PROPOSAL_AMBIGUOUS, result_count, 0)`，不是有效ReplyOnly，也不是资金拒绝。
- [harness.py:582—596](../../backend/app/agent_platform/harness.py#L582)先写失败`model.finished`，随后将原异常统一包装成`ValueError(MODEL_UNDERSTANDING_FAILED)`。该理解在[698行](../../backend/app/agent_platform/harness.py#L698)执行，早于[720行建任务](../../backend/app/agent_platform/harness.py#L720)，所以无平台任务。
- [API service.py:815](../../backend/app/api/service.py#L815)已有`MODEL_PROPOSAL_FAILED`受控失败发布与`error_completed`分支；但当前异常逃至[无任务通用恢复分支](../../backend/app/api/service.py#L839)，用户得到无法确定原消息处理结果的固定提示。`error_completed`同原请求仅重放，不重新调用模型；F06历史与SSE错误由稳定ID发布。真正中断、没有持久结果的请求仍须按未知结果处理，不许自动重理解。

## 只读回放

[`test_replay.py`](test_replay.py)从外部原JSON只读加载三条assistant文本到内存，用脚本ChatModel回放到真实DeepAgentPlanner及真实ASGI/ApiService/Harness；不调用provider，不改prompt或严格guard。

- 首批6个检查，**3 passed /3 failed，6.23s，exit1**：3项确认严格门仍拒绝0 outcome；3项故意红在候选固定提示尚未出现。每条红例在失败断言前均确认同UUID重复两次仍只有一次脚本推理、0任务、0银行submit及0风险gate，原自由回复不进入历史。
- [原始JUnit无损gzip](replay-results.xml.gz)，解压SHA256 `19425AA84C4FED8C5814A1D3CF96B9927C7D444316563AAA81628B6B81427201`。红例中的长提示仅是当时方案候选，后续实施票按获批日常话固定文案再验证。
- 随后独立API消费接缝探针 **1 passed /3.52s，exit0**：用公开Harness入口的明确替身返回既有`MODEL_PROPOSAL_FAILED`失败ModuleResult，不建平台任务；真实API正常发布固定reason，同原request不重复消费。[原始JUnit](api-contract-probe-results.xml)，SHA256 `57741A2297DB45B3F6872E9EA8D8D94570F7D85608BFF168C7262BAE3D6A6371`。这证明消费接缝已存在，不是生产修复绿例。

回放依赖环境变量`BANK_PROTOCOL_OBSERVATION_JSON`指向原外部JSON，`PYTHONPATH=backend`，关闭本次子进程的LangChain追踪；执行`python -m pytest .scratch/v05-model-protocol-diagnosis/test_replay.py`。探针是随后追加的独立节点，首批6项与单项探针分开记数。

## 最小方案

1. **首选，已获批：平台内受控失败结果。** 保留model.py全部严格校验与失败审计，在理解/分类边界仅识别明确`PlanningError`并保留其安全类型；早于建任务返回现有`MODEL_PROPOSAL_FAILED`失败ModuleResult，reason使用固定日常提示。API现有分支发布并完成原消息，不必改API/契约。原正文不变成ReplyOnly，不补proposal或字段，不重跑原UUID。实现另开平台票14，先等335合入，再基于新main修改必要harness接缝。
2. **备选：API分类已知理解失败。** 在无平台任务且收到明确`MODEL_UNDERSTANDING_FAILED`时固定错误提示，其他中断仍保留未知恢复语义。需要独立API实施票；当前包装已丢失stage/count，若消费这些细分诊断，必须另立平台公开安全错误的前置票，不能假定API能直接catch原PlanningError。

两方案都不声称账户安全、已拦截或资金结果，不将固定B的3 Failed改成Pass/资金BLOCK。不强制未经验证的provider `tool_choice`，不改模型、prompt或B/C历史；若以后观察真实集成效果，应另行新批并与脚本层分开。
