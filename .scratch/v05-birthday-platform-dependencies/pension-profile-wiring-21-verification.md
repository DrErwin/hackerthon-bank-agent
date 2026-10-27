# 平台21：实际验证与待API22接缝

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
| 原失败再现新批，固定960源码 | 1 failed /18 deselected，10.06s | 同API父来源缺口，真实0 bank_operations；api22-red-repro.xml.gz及[实际只读观察](evidence/2026-10-27-platform21-api22-red-observation.json) |
| 平台目录广回归，固定960源码 | 483 passed /13 skipped /1 deselected，491.11s | 唯一deselected为待API22的完整P01；13项为原有skip，不把排除项或skip写通过；platform-before-api22.xml |
| 安全相关三文件，固定960源码 | 189 passed /7.58s | security/test_pension_demo_risk.py、test_demo_text_risk.py、test_risk_detector.py；原A2与安全20仍通过；security-boundaries.xml |

表中所有文件均在本组evidence目录，完整名以2026-10-27-platform21-开头；[原证据索引](evidence/2026-10-27-platform21-evidence-index.json)逐项记实际JUnit、SHA-256及gzip解压原文hash。控制台时间与XML testsuite.time有pytest记账差异，不改XML来对齐。

含失败正文的原XML带CRLF，仅用gzip空文件名/mtime=0无损封装，核对解压逐字一致；原XML副本在本地外部platform21-original-evidence中。没有改失败期望、把失败当跳过或用新批覆盖旧批。

## 发现的真实API缺口

ApiService.trusted原先始终构建parent_task_id=None；初始Harness.dispatch_child有可信parent，故新profile可到MEDIUM确认，但HTTP批准/验证重建child上下文后19正确拒绝缺source。持久父子关系、step/plan、两个capture标记均在，不能为此放宽19。API22由中控在独立目录票处理；本票保留完整两笔原断言。

原pytest-4335失败批使用pytest默认临时根，随后被框架保留近几批的自动清理机制清掉；原XML和当时实际审计工具输出保留，不能再声称原库在位。为保留数据库，固定960源码另跑上表api22-red-repro新批，事先核对独立basetemp不存在且在自有外部evidence根内，未复用或清理旧目录。

该新红批实际本地目录为platform21-original-evidence/api22-red-repro-20261027-01/test_p01_two_medium_transfers_0，不受默认pytest轮换管理；数据库只读核对integrity_check=ok，应用SHA-256 2c54c2603de16bae388dea3f7844ca1618ed722ca019bcb7020c907b71f812bb，银行SHA-256 c1e1a8d1ad4e559bcee0e9c5e0762f9ad96f54c5f42fcb5d0474a5399786eef8。真实银行0操作，A1=500000分、A5=0分，两边capture版本均为risk-conversation-uuid-text-1；先MEDIUM确认再缺来源PAUSE的实际裁决和原operation见只读观察JSON。

## 验收边界

已证明配置只读、默认None、literal错误脱敏、完整新来源和hash、任一历史/错误capture不继承、无ID文本不伪造UUID、未知/危险/异参拒绝以及原A2保持。父/子来源仍全部消费19真实校验，没有因为profile换成宽松fallback。

完整P01采用本测试新银行的当前可用余额5000元范围，准备A1余额500000分、A5为0；这不是实际养老金入账证明。要求仍为两笔250000/100000分逐笔确认和code+face，重启沿原号不多写，最终A1留150000分、A5为250000分。本轮这一完整断言仍受API22阻塞，后继精确组合结果另补；不得先称真实闭环完成。

运行时默认不开，确认/验证/执行器规则不改。新profile十二维为明确模拟，真实银行收款人两维缺失仍unknown；AI/脚本模型/本地回归、真实GLM、页面与真人安全接受分别记录。旧96/B/C结果未改变。
