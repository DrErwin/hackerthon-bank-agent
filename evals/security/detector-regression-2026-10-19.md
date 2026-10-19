# 真实检测器离线专项

Owner：Ringo。实施票[v04-ringo-security/03](../../.scratch/v04-ringo-security/issues/03-attack-observers-and-adapters.md)，来源Issue #86/#88/#160。依赖检测器PR #169和MAT材料PR #163。本PR只改evals/security，复用真实HTTP入口和安全执行链。

## 结果和范围

`detector_regression.py`将SEC-T-003/004/005原v01话术及MAT-FRAUD-01的SEC-T-003/v02原文各跑3轮，共12轮；另跑1个合法对照。可信输入读取、检测器、安全门及模拟银行均为实际实现，规划器使用固定转账提案，读授权回调沿用平台夹具。写动作的风险等级来自实际文本及银行事实。

最终12轮专项检查通过，合法对照通过。高风险任务FAILED且实际BLOCK，规则和检测器版本可追踪，恢复保持终止；银行提交尝试为0，独立账本保持。合法对照因未知事实PAUSE/NEEDS_ATTENTION，这项仅验证未误判高风险，未据此认为正常业务完成。原文排除在审计和JSON结果之外。

12轮整例继续Blocked，真实模型解释和所提工具请求待验，用户风险提示与下一步待复核。未改137/294/356全集分母或历史结果，专项Passed与整例Blocked分别报告。

## 原始报告

| 批次 | 专项结果 | 解压后sha256 |
|---|---|---|
| [初次](evidence/2026-10-19/2026-10-19-detector-initial.json.gz) | 12 Failed及对照Failed | 4B3B92B9A74F9979AEC38D048639B2917C163315E8EFD01DA06D800816125EEF |
| [修订后](evidence/2026-10-19/2026-10-19-detector-final.json.gz) | 12 Passed及对照Passed，整例12 Blocked | 514263805A207C73D265E54A988C8D62188B601F9F8D03751610204A118F094C |

初次失败是适配器将契约小写decision与大写比较，其他检查通过；已修正，历史报告保持。台账retest_of关联initial文件及上表完整指纹，原JSON未追加此字段。运行源为本地安全e4a496a、平台/API main e43765a并含PR #149/#165声明修复，实际来源文件SHA256在原报告，未声称纯main检出。

## 复现与待补

Spec初审发现整例状态必须让实际Failed优先于缺证据Blocked，已返修并新增失败探针状态断言。修订前两份报告保持，最新[固定复验](evidence/2026-10-19/2026-10-19-detector-retest.json.gz)的解压sha256为`A74C92FDE599BF7DADD7FF535BFBCACBEDFCE66C799B8FFC1BFC095C499515D8`，专项12 Passed、合法对照Passed、整例12 Blocked。本台账retest_of关联上表514263805A207C73D265E54A988C8D62188B601F9F8D03751610204A118F094C。

全security目录69 passed（143.59秒），返修后的5项专项测试独立通过（14.61秒）。后端检测器PR #169精确head fb24cfb的GitHub CI为945 passed，模拟银行评测14 passed。本专项结果独立于CI登记。

main 399a2fe记录PM决定A：本期Demo沿用固定等级夹具，真实检测器仅离线评测，生产装配转v0.5且不采集设备信息。本PR遵守该决定，未改演示装配；真实识别未接入演示的限制保持。

在可导入PR #169及main e43765a backend的环境运行`python evals/security/detector_regression.py --output <仓库外的新报告路径>.json`。报告及工作目录独占创建，模型调用0次，eval.invalid仅作静态标记，runner没有外部网络调用。

工具返回、不可信资料和记忆摘要的实际模型载入观察仍待相应入口；其余MAT材料与既有11轮报告保持Blocked。当前新增适配器不把直接聊天替代这些入口，也不替代真人安全批准。
