# 入口修复303/304与E2E设计接收记录

日期：2026-10-25。Status: delivered / awaiting_combination_and_owner_merge_decision。

两项开发已分别回交，不是新的S01验收通过；未获合入或本批CI例外，不借用第三批293/299批准。

| 原问题 / PR | 固定交付 | 范围和实际证据 |
|---|---|---|
| Issue301 / [PR303](https://github.com/DrErwin/hackerthon-bank-agent/pull/303) | `cb16311c590829509b6c759190aff7f522fec1e1`，Draft/main | `agent_platform/`三文件及自有材料；按完整生活目标区分联动、单项、查询和澄清。新隔离真实GLM修前1例失败、修后13例路由通过，均0业务任务/0银行操作；没有HTTP或页面办理 |
| Issue302 / [PR304](https://github.com/DrErwin/hackerthon-bank-agent/pull/304) | `60f06860dc34255bc6f3290efdeb82dbc5895d49`，Draft/main | `modules/subscription/`五文件及自有材料；明确停止/不续费走原对象选择、确认、验证，查询/否定保留只读。132唯一节点通过：55新Fake工厂、6新真实Harness/安全门/执行器/隔离MockBank集成、71既有回归；脚本模型，不是新真实E2E |

## 中控已直接核对

- 两个PR准确head、目录边界、未合状态及原聊天中的两位独立子代理活动。303受审af27541至交付head平台代码无差异；304受审baaa3af至交付head订阅代码无差异，必须项均闭合。304历轮否定范围、旧批量、分句及后果/日期询问缺陷均有失败与修复记录；不把“确认前零写”掩盖错误意图分类。
- 303两份JSONL按manifest复算SHA-256：修前`2019adfab655130bbc3c65d92c936d957a846df1a9f0e8f7a77a734a592d04cc`，修后`6e1f2a961d78d6b91574585d2bd9ad28c467c4c2d2bc914dae170d38e96753b4`。修后13条expected与actual一致，银行操作/业务任务均0；model.py哈希`3d164e0cdad36fecd26972253d8c7058c2a711fb55729f41b52b540ba425e744`。原CRLF字节在bd40c96保留，原PR300失败没有覆盖。
- 303的20、68、1、7程序回归存在重叠，不能相加；13 live是理解层小样，不是整体成功率。中控未重复调用模型或运行测试。
- 304直接解析原JUnit：132节点/132唯一、0失败/错误/跳过，SHA-256 `c53f060f3a496a8f479153c23614944f0b45e5edcfbf1735b3dce1d26226ff8f`；聊天实际命令退出0、132 passed / 21.24s。原reproduce.py/probe-result.json/existing-tests.xml/existing-tests.console.txt与74da8d9逐字节相同。
- 两准确head的CI annotation均为账户付款/额度导致job未启动：303 run40190238859/check121159485732；304 run40193633934/check121169705294。CI=Blocked，Ubuntu标签notice另列；无远端测试执行证据。
- 303连接器一度给mergeable=false，中控只读`git merge-tree --write-tree origin/main cb16311`退出0，未发现与84a3605冲突；不把缓存/计算状态当成代码冲突。没有修改或合入原分支。

原材料分别位于两个PR的`.scratch/v05-cross-platform/research/issue301-diagnosis.md`、`issue301-review.md`及`.scratch/v05-s01-subscription-diagnosis/implementation.md`、`review.md`。实现前后证据不复制为中控新测试。

## 一次必要的局部组合核对已分派

原平台对话已收到任务：新隔离验证worktree固定最新main + 303/304各自补丁，运行去重后的必要受影响局部程序测试。两个修复共用订阅运行验证路径，需核对组合后的调用/断言；不更新原PR、不跨目录修新代码、不带300观察器/296或生日规划。

明确不启用BANK_ROUTING_LIVE_CONFIG，不调用模型，不开HTTP/页面/真实E2E，不跑全后端；只新绝对临时数据目录。原13 live默认skipped单列，原13真实路由与132仍归各自版本。已有完全同树结果可复用；新增代码问题回归属作者。两位独立子代理核对组合来源、实际结果和规格/证据适用后回交并停止。当前尚无组合最终交付，不预报通过数量、不提前申请或合入。

## 设计交接和暂停状态

- E2E原对话本地`217c616`的七份规划Markdown已接收，实际双轴静态复审0必须项，执行者已停止。入口：[Erwin后续手工执行交接](../v05-cross-e2e/manual-execution-handoff.md)。中控只取七份文档，未带入未批准PR300的Python、JSON、gzip、图片或原始失败附件；不存在于main的PR300引用改指固定31e995e，并明确观察器尚未合入。原`planning-approved`标记改为`design-reviewed / execution-deferred`，不冒充本人方案接受。
- 生日G3提供稿本地`21e16ae05d26eb12739a3a4a86c284bd60349c49`的六份Markdown已接收，双轴静态0必须项。补齐无edit/source初始根、普通输入/事实/异常后继同等封存发布，以及旧显式quantity=1的可核验兼容；仅设计，无实现/运行或最终消费方签收。G1/G2仍待本人，01—05/08未激活。
- 前端02由waiting变为idle/interrupted，视觉未完成，不能记录仍在跑。已向原对话仅续派静态整理现有原型/方案、缺口、两轴审查和本地交接后停；不重试浏览器/预览、不绕过工具许可、不改生产前端。本人页面走查批准仍缺。
- 银行、安全、预算前置三线已明确停止，保留原成果与未满足项。cross06仍开发；本轮没有新真实E2E、代码合并、共享迁移或安全政策生效。
