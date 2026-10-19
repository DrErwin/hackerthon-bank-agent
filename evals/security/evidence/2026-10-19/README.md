# 2026-10-19 安全覆盖扩充离线证据

本批对应v04-ringo-security/01及Issue #88，AI按Ringo授权执行。原始JSON以gzip保存，解压后sha256为`2B6712362DCB5FC7F951B300F7F0D49A4BEB31983D1F2F0471CEB729E44937B9`，原报告内容保持。

## 执行与判定

入口：`python evals/security/security_runner.py --output <仓库外唯一新路径>`。使用Python 3.13.5，固定离线规划器，实际模型调用0次。模拟银行与服务实际执行，风险事实使用受控夹具，真实攻击识别尚待评测。

分母137主用例、289参数实例、345计划行；实际20 Passed、0 Failed、325 Blocked、0 NotRun、0 PENDING_SPEC。新增15个主用例的逻辑步骤尚未接入场景适配器，缺口按Blocked保留；其数据设计状态仍为NOT_RUN。B18只覆盖已撤销工具的三次调用拒绝及零副作用，预约保留及自然语言误映射仍缺观察，因此整体Blocked。

## 来源及代码限制

本地工作副本由GitHub连接器取得UTF-8源码，工作根目录没有完整Git对象库。报告中的`code_revision=unavailable`及`source_manifest.all_blob_hashes_verified=false`如实保留。`source-manifest.json`中另记连接器核对：原冻结提交`5d035e50e5d5031eff80f3bf8d608f5c9b09c9ac`的七份来源blob均匹配。这项外部核对与运行器内的Git核对是两类证据。

后端为远端`c20553e380385046dd24a96a49c53803671e55ed`快照加账单安全PR #149的重基前版本，本地后端提交`4ca3f5a`；评测代码及数据固定于本地eval提交`53d948a`。本批未包含随后main新增的订阅工作线，最新main联合验收仍需另跑。PR #149后续重基不改变本批历史。

| 文件 | 本批sha256 |
|---|---|
| security_runner.py | 86D03CE602D35A74D2B5E19E06C1E252F97DEC59E134C296FD81111BB495705E |
| cases.jsonl | B1F0C428C1889070449B020F0796DEABD9F652169FBA880B9F917606D91056C7 |
| source-manifest.json | D37980C45A44FDDB74592B1BF2F8E66C0A820D27230440124F5811B84ABCCDB3 |
| run-results-template.csv | D0A6D11BD2485C4E78E4712FEF4984627DE6AE68A6EEFBB8DFB230DF70185B4B |

此前122/274/330报告及本次20/0/325分别保留。运行器缺观察即Blocked；两轴AI审查的遗留问题归零与整体验收通过分别记录。真人专业签核仍按项目门槛进行。

2026-10-20 返修说明：本批为固定数据快照；其后 `cases.jsonl` 仅修订 SEC-M-009、SEC-D-010 两条用例的步骤与预期文本（当前 sha256 `4e039afefe2750979f64d14537fcd5d56d2ef1931c6c635be0adf5005c21c44a`），二者执行状态仍为 NOT_RUN，本批 20 Passed / 0 Failed / 325 Blocked 及原始报告保持未重跑。
