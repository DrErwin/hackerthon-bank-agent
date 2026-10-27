# 平台21：实际验证与API22精确组合

Ticket: [v05-birthday-platform-dependencies/21](issues/21-pension-profile-wiring.md)
Spec: [P01显式profile与完整来源](pension-profile-wiring-21.md)
Date: 2026-10-27；AI验证，非真人安全接受

## 固定来源

基线ed1596d57a5b1092a324b6d3013b1367b403cbec已含19/20。实现固定commit 960dfb4348f1d73668a13af1911cca00c30bdb3e，agent_platform tree 2cb5735d4adbbcc91a4b46450a1fe2901f7220a2。只有平台和自组21票据，security/API/Cross/私密配置不改。

所有测试用现有Python，PYTHONPATH明确指向本工作树backend，PYTHONIOENCODING=utf-8。PensionChatModel仅给出脚本工具结果，经真实DeepAgentPlanner/schema进入真实API、Harness、持久关系、安全20、确认/验证、执行器和MockBank；不是GLM识别或浏览器证据。只新隔离数据，未运行外部模型或更改共享库。

## 递进记录（不相加刷分）

| 批次 | 实际控制台结果 | 说明与原始证据 |
|---|---|---|
| 进程配置首例，未提交工作文件 | 1 failed /4.94s → 1 passed /4.24s | 缺字段AttributeError后显式literal生效，原文件字节不变；config-red.xml.gz / config-green.xml |
| 首个实际P01接线用例搭建 | 各1 failed /5.40s、11.56s | 前者漏选养老金场景，后者把同模块只读子任务计成转账；仅修测试路径与实际operation过滤，原flow-red.xml.gz、wiring-red.xml.gz均保留，不算产品红绿 |
| 正确P01首次到真实门 | 1 failed /10.10s → 2 passed /9.11s | 原门needs_attention，接线后新父/子MEDIUM确认；第二批还含配置首例，非两笔完整闭环；real-gate-red.xml.gz / first-wiring-green.xml |
| 无原request_id的普通text | 1 failed /6.07s → 1 passed /9.44s | 原完整标记未失效；修后置None、历史保留、业务继续并采用后PAUSE，真实revision无误CAS；noid-red.xml.gz / noid-green.xml |
| 首个19项目标批，尚未提交工作文件 | 18 passed /1 failed，77.23s | 完整P01第一笔HTTP批准丢父来源，risk-input-request-binding-required；targeted-first.xml.gz，不能称闭环通过 |
| 原失败再现新批，固定960源码 | 1 failed /18 deselected，10.06s | 同API父来源缺口，真实0 bank_operations；api22-red-repro.xml.gz及[实际只读观察](evidence/2026-10-27-platform21-api22-red-observation.json.gz) |
| 平台目录广回归，固定960源码 | 483 passed /13 skipped /1 deselected，491.11s | 唯一deselected为待API22的完整P01；13项为原有skip，不把排除项或skip写通过；platform-before-api22.xml |
| 安全相关三文件，固定960源码 | 189 passed /7.58s | security/test_pension_demo_risk.py、test_demo_text_risk.py、test_risk_detector.py；原A2与安全20仍通过；security-boundaries.xml |
| API22合入后的必要精确组合，固定a771bd4f | 6 passed /13 deselected，53.75s | 完整两笔中风险+四项缺/错capture经HTTP确认仍拒绝+legacy重启仍未知；[api22-combined.xml](evidence/2026-10-27-platform21-api22-combined.xml)和[实际只读观察](evidence/2026-10-27-platform21-api22-combined-observation.json) |

表中所有文件均在本组evidence目录，完整名以2026-10-27-platform21-开头；[原证据索引](evidence/2026-10-27-platform21-evidence-index.json)逐项记实际JUnit、SHA-256及gzip解压原文hash。控制台时间与XML testsuite.time有pytest记账差异，不改XML来对齐。

含失败正文的原XML及原只读观察JSON带CRLF，仅用gzip空文件名/mtime=0无损封装，核对解压逐字一致；原XML/JSON副本在本地外部platform21-original-evidence中。派生索引以LF写入，不改任何原证据。没有改失败期望、把失败当跳过或用新批覆盖旧批。

## 历史发现的真实API缺口

ApiService.trusted原先始终构建parent_task_id=None；初始Harness.dispatch_child有可信parent，故新profile可到MEDIUM确认，但HTTP批准/验证重建child上下文后19正确拒绝缺source。持久父子关系、step/plan、两个capture标记均在，不能为此放宽19。API22由中控在独立目录票处理，现已通过[PR #350](https://github.com/DrErwin/hackerthon-bank-agent/pull/350)合入；原失败证据与本票两笔完整业务断言保留。

原pytest-4335失败批使用pytest默认临时根，随后被框架保留近几批的自动清理机制清掉；原XML和当时实际审计工具输出保留，不能再声称原库在位。为保留数据库，固定960源码另跑上表api22-red-repro新批，事先核对独立basetemp不存在且在自有外部evidence根内，未复用或清理旧目录。

该新红批实际本地目录为platform21-original-evidence/api22-red-repro-20261027-01/test_p01_two_medium_transfers_0，不受默认pytest轮换管理；数据库只读核对integrity_check=ok，应用SHA-256 2c54c2603de16bae388dea3f7844ca1618ed722ca019bcb7020c907b71f812bb，银行SHA-256 c1e1a8d1ad4e559bcee0e9c5e0762f9ad96f54c5f42fcb5d0474a5399786eef8。真实银行0操作，A1=500000分、A5=0分，两边capture版本均为risk-conversation-uuid-text-1；先MEDIUM确认再缺来源PAUSE的实际裁决和原operation见只读观察JSON。

## API22后的准确来源与银行事实

机械rebase到main ef8f92203787e7d5bb6184e3b59230c479614817后，原960/ddc9/43ccc三个提交的range-diff全部等价，平台tree仍为2cb5735d4adbbcc91a4b46450a1fe2901f7220a2（重基head 24f9dbee20eeec35a840afc1eaa9ce7a5141779f）。生产文件未再调整。

测试脚本原先给终态任务发F15查询，这是错误入口；按现行契约改用GET读取原task/op，并加F15终态409断言，保留原号、receipt与资金次数全部断言，也清除两个未用测试import，没有放宽生产allowed_actions。实际精确组合source为a771bd4fb0ed7265e464287615d560e6db5141b8，API基线为上列ef8f9220，平台tree 037585fe0dacf787ed1cb6efd5640b9c71f62a14，测试blob a0c3ed6be95ec5c4c1f595c4ddd4d96521a223bb；与原平台tree相比仅该测试文件改变。

只复跑API22会影响的6项，没有无理由重复483广回归、配置首例或189安全相关回归。实际结果6 passed、13 deselected、0 failed/error/skip；JUnit SHA-256 f6ee2225962533855acbb5c2f8331b50283c327a4c41fdfb74b2e9fd7b404d4d，观察JSON SHA-256 c3f16fd7eb5ca732275f663e64c7dbb92a1a3fc596a0eba51b61382a3888641e。

新组合的basetemp事先核对不存在，固定在自有外部platform21-original-evidence/api22-combined-20261027-01，不复用红批或默认自动清理目录。六个用例的应用/银行库均只读核对integrity_check=ok；五个历史/错误capture拒绝用例银行操作均0。完整P01用例实际只有两笔bank.submit_transfer，均succeeded，分别250000/100000分，各经过自己确认、code、mock_face；第一次code通过而face未过时零资金，非管理者face-result仍403，同face回执重放不多写。第一笔成功后关闭并重建应用，原task/op/receipt不变，再办第二笔，两个challenge不同；最终父任务succeeded、安排解除，A1=150000分、A5=250000分、冻结均0。

完整用例应用库SHA-256 b8dd68e1157f6081a699393d147b9a3d1e8bd4e9fa0840a5e5eec3830837f801，银行库SHA-256 8bec68d8e4140579d59ff46fbb26d726a67f4fbbeb79f1db8ff6bf016ac722bf。只读观察记录两个真实原operation、各自确认来源和已通过双因子、风险裁决与银行事实，不包含验证码值或秘密。

## 验收边界

已证明配置只读、默认None、literal错误脱敏、完整新来源和hash、任一历史/错误capture不继承、无ID文本不伪造UUID、未知/危险/异参拒绝以及原A2保持。父/子来源仍全部消费19真实校验，没有因为profile换成宽松fallback。

完整P01采用本测试新银行的当前可用余额5000元范围，准备A1余额500000分、A5为0；这不是实际养老金入账证明。两笔250000/100000分逐笔确认和code+face、重启沿原号不多写、最终A1留150000分及A5为250000分已在上述脚本模型组合核实；真实GLM/页面仍待中控后继，不将本结果写成真人接受。

运行时默认不开，确认/验证/执行器规则不改。新profile十二维为明确模拟，真实银行收款人两维缺失仍unknown；AI/脚本模型/本地回归、真实GLM、页面与真人安全接受分别记录。旧96/B/C结果未改变。
