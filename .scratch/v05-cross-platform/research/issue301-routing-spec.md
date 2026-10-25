# Issue #301：生活目标与单项业务的入口区分

Status: in_progress — 已授权平台内诊断、最小修复、针对性验证与独立PR；不授权合并。
Owner: Erwin；Execution assignee: Codex；Accepted at: 2026-10-25。
Package: [v05-cross-linkage/packages/01-platform-bank：公共接缝与模拟银行](../../v05-cross-linkage/packages/01-platform-bank.md)
Source issue: [Issue #301](https://github.com/DrErwin/hackerthon-bank-agent/issues/301)
产品基线：最新origin/main `855497fa16616595eac8cfac9013ec701ffe942d`。

## 问题与证据

老人想“弄清支出、处理不用的扣费”，系统却进入单项退订，最后只给签约清单。HTTP成功和单项任务办结没有完成这个目标。
原失败固定在PR300 head `31e995e75c12af57e05ae8cc9cda56b3da2d9693`；完整报告`evals/cross/evidence/2026-10-25/s01-live-20261025-01.md`及同名json.gz均用git show只读，原解压JSON SHA256为`95cf45a276d56bd5812467e5bf616289499d76b93d09ce2081a85ce630a75f87`，已重算相同。
原请求含完整原话与cross.start_task；实际模型返回subscription.cancel_subscription，invalid_tool_calls为空。没有网络或解析错误；程序后续按此选择派发。原失败不修改、不重命名、不覆盖。

## 目标与范围

遵循[联动PRD](../../../docs/prd/06-跨场景联动-PRD-2026-09-23.md)§1.2—1.3：根据用户想完成的目标选择入口，不要求点名模块。完整生活目标交现有联动能力；明确单项退订、只读盘点仍交原业务；确实分不清意图则澄清。缺商户、金额等字段不自动把已明确的业务意图变为闲聊。
只改backend/app/agent_platform/与本票/证据。先核查原模型输入、目录、候选与派发，证明缺口后再修；不堆关键词、不硬匹配原句、不强制全部订阅走联动。若必要能力描述归其他目录，回交具体差异，不跨目录改。
不改API/订阅/Cross/安全/银行/评测期望或#160。生日依赖01—05无实施授权。共享跟踪、completion由中控维护。

## 场景与验证框架

| 场景 | 判据 / 验证层 |
|---|---|
| R01 | 原减支表达及不同语序/措辞、无显式模块名的同类生活目标选cross；保存新批次真实模型选择，不把替身当理解证据 |
| R02 | 明确某项退订、仅关续费仍可选subscription.cancel_subscription；只读签约盘点/扣款查询选对应原只读能力 |
| R03 | 真正不确定的请求先澄清；有明确办理意图但字段不足仍走原任务补齐；不靠目标关键词抢走单项任务 |
| R04 | 养老金、生日目标与普通转账的原入口保持；模型提议/解析/派发分开检查 |
| R05 | 仅有注册能力才提供相应路由，现有唯一结果、继续原任务、权限/确认及异常规则保持 |
| R06 | 针对性替身/真实程序接线、真实模型路由、真实页面S01和真人接受分别记录；模型探针只理解不派发，银行写/操作/结算均0 |

本票运行最小反馈探针、相关单文件测试及受影响路径，不循环跑全量。真实模型用隔离库/会话及既有本地秘密配置，原风险事实不更改，秘密/验证码不输出或入库；有失败如实保留。
平台PR合入后，由原[v05-cross-e2e/01：减支E2E](../../v05-cross-e2e/issues/01-expense-reduction-e2e.md)在新批次真实页面复验。本票局部通过不关闭E2E、S02—S05或体验/安全接受。

## 流程

票号15经本地/已取回refs历史核对未占；14为原订单来源门，不能复用。开发票见[15](../issues/15-life-goal-routing.md)。
本机已读取to-spec/to-tickets/implement模板；它们disable-model-invocation，本会话没有斜杠入口，按用户已明确实施授权手工执行同等步骤，不声称已调用。使用diagnosing-bugs定位，独立Standards/Spec两位子代理复核，修完必修后自己的PR回交；不自合并，不继承其他PR的CI例外。
