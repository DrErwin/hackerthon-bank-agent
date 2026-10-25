# 平台提供条件：文档核查与双轴审查

Status: g3_design_reviewed / implementation_blocked — 本轮初始/普通不可变源及旧单件兼容设计双轴复核通过；G1/G2及G3真实提供仍待闭合，原四票及新增05全部planned/blocked；未实施。本轮按停止线回交后即停。

固定源码main：`af779df431a7f650851ffe3e2ede8b763dcdb1c5`。
文档审查base：`dab17d030b4a4a481280d5cc5900176db38c9aeb`；只快进中控文档，没有运行代码变化。
固定Cross材料：`1d7f1fab8d5e2622c1d319e178abf9f1654fc73c`的三份完整Markdown。
本工作组仅新增spec、本记录和四张单目录计划票，不修改任何原票、产品代码、测试或组合/审计证据。

以上为初轮记录。当前收口基线`3239fd75417e8f1e47aea0c0db83d734cdfffe6c`，本地分支`codex/v05-birthday-dependency-closeout`；修改本组规格/四票/记录并新增一页decision。原跨组票、bce306d安全原稿、代码/测试/PR、共享进度及审计原材料均不改。

## 初轮静态检查（历史，截至dab17d0）

- 编号：已查main及取回的未合refs，platform13/14已占，使用尚未存在的新工作组01—04；security原01/04非撤离能力，不重复其交付。
- 能力：数量/执行项/展示是平台接线；非终止式原子撤离需security；当前F10/普通draft不能承接等待态编辑，API接入须先完成契约§8确认。
- 范围：不新增数量公共字段/任务枚举；现有AppStore快照/CAS尚无确定缺口，不预建storage票；如需模型变更再交contracts目录。
- 事实：所有调用拒绝及并发判断均为源码推演，本轮未跑测试、模型、全量或CI。
- 首轮六份材料41个本地链接/锚点、票号与围栏、差异空白检查通过；跨组前置补全后最终44个本地链接/锚点、编号、格式及差异空白检查通过，仓库原链接检查也通过。
- 最后fetch核对main仍为dab17d0；相对源码基线af779df，backend/evals/正式契约/PRD没有变化；PR296仍b41ef64、PR298仍5ebc133，均Draft/未合并，未修改。Cross三份main材料与固定1d7f1fa的blob分别相同。

## 独立审查

固定初审提交：`6a908171d713f5fa2368ab7bfa3897dd79627cb4`，基线dab17d0。

- Standards初审：1项票据引用必修、0建议；01/03的Cross08和04的预算来源API02须在Blocked by补完整票号/标题/链接。已补齐，只修引用，不改变依赖关系。
- Spec初审：PASS，必须项0、建议0；完整核对数量/执行项/原子撤离/失败与未知边界及四票拆分。
- 作者静态补核：冻结验证前可能已存pending_freeze限定授权；补齐合法撤离后按原绑定处理未生效授权、不得挪用或清除active真实收尾，后续停止不得把确定未提交永久记未知。仅将此要求纳入G2待审与未来验收，未实施状态修改。
- 修订提交`c1f1cc38b6a6579477818da8a5e3d50a89f76913`两轴复审：Standards PASS，原1项必须项关闭，新增必须项0、建议0；Spec PASS，必须项0、建议0。此后仅回填本记录。
- AI审查不代替G1契约协同、G2本人安全审阅或G3提供方接口确认；两位初审/复审均只读，未执行源码/测试/模型/CI或改文件。

## 回交边界

本地提交后交中控读取；不推送、不建PR、不向其他对话发送消息。实施需明确授权和真实前置能力交付，planned/blocked不构成开工许可。预算API02按中控既有分派另行推进，本轮不处理；cross06/Cross08及本组四票不因本轮材料改变实施状态。

## 本轮安全依赖收口（2026-10-25）

精确来源S-G2：本地`bce306d07e429b8ce604dd8232fa58cd3836f0a3`，父f21db3b00c6365132323f85b104c184a88aa4a20，基线41c01ae，路径`.scratch/v05-birthday-security-review/review.md`，blob`53f9196dc9d2a16c1bc92b6235902b840fc3343a`。只读原稿全文，不复制覆盖或声称本人接受。

- 纳入迟到grant/pending/bind/平台指针、preparer发码与登记窗口、旧挑战失败/到期、完整旧确认版本、同事务必要审计与断点恢复。
- 区分现有约束与G2-A/B/C待选新语义；decision列完整范围和首批收窄两项及代价，不采用安全稿的收窄建议作为最终范围，不删除验证码/验证态原要求。
- 自查银行verification.create_verification也按同task旧failed/动作expired拒绝，完整方案须两侧收口，不能只改gate；跨库可靠胜序未证实，必要提供目录差异待本人选择后明确，不在四票里越界编码。
- G3给出原operation复用为attempt、显式执行回传、最小项/历史快照、两种编辑依据、旧单件与明确失败路线；只供Cross08核对，未代其确认。
- 本轮首轮文档检查：七份Markdown、53个本地链接/锚点、四票编号/blocked状态及差异空白通过；未执行源码、测试、模型、CI。
- 本轮受审提交`9ea40725e93fd7d5f87967884fa1e27804a34164`：Standards必须项0、非阻塞建议1（初轮“最后fetch/PR未合”须标历史，已改标题“初轮静态检查（历史，截至dab17d0）”）；Spec PASS，必须项0、建议0。与初轮结论分别记录，不代表G2本人接受。
- 作者补明G3原grant/bind必须捕获原pending.operation/确认版本，不能迟到后按当前freeze键重挑原动作；仍只是Cross待核对的兼容签名，无代码变动。
- 修订`02b1a6ea29857f8acd6abae34114362f8d7572be`补核：Standards PASS，原非阻塞建议关闭，剩余必须项0/建议0；Spec PASS，必须项0/建议0。两位均只读，不执行源码、测试、模型、CI或改文件；此后仅回填本记录。
- 最终七份Markdown的53个本地链接/锚点、票号、围栏、四票planned/blocked及差异空白通过，仓库链接检查通过。最后fetch主线`c02c70d476f04d5d788c7c5852bc613efc3dc66f`；相对本轮基线3239fd7，所核查security/audit/银行verification/生日runtime/contracts/正式契约/PRD无变化。主线推进不冒称本材料已获实施或本人安全接受。

## G3消费方对账收口（2026-10-25，当前轮）

- 精确消费方原稿S-G3：本地提交`e4cb7b7dad5ef78b31e52c64e845f7db8a55ea78`、父c0752632f088857838661b13739ce2170466f0e6、产品基线2a070b9；完整路径`.scratch/v05-cross-business/birthday-g3-interface-review.md`、blob`3ae7559a14f36b1e501f274b8d0f36baed510f33`。已全文只读；原稿不改。
- 新增[g3-reconciliation](g3-reconciliation.md)：区分已一致方向、提供缺口、本人政策；明确先受理预留、后安全依据、隔离候选、持久单胜者、同次task CAS发布及普通/异常恢复只读已发布源。原operation经过check/execute/grant/bind的捕获与显式消费列成表；接口名/签名仍待Cross确认。
- 静态核查main c02c70d：现saver精确ID读取并不保证通道值不可变，已有put会覆盖同namespace/channel/version；据此新增[05存储窄票](issues/05-immutable-edit-checkpoint.md)，而非预设通用框架。memory归属/namespace透传可复用，未证实另需memory票。
- 03增加05真实前置；双方先确认设计、05可先实现，03/08再接线，不互等对方代码形成环。旧源缺失或无法核验不回latest补证；新协议首次可办理状态建立完整published_ref。完整原要求及G1/G2未决保持，原01—04和新增05均planned/blocked。
- 本轮仅本组Markdown；不改Cross08、安全原稿、业务/安全/银行/评测代码、共享跟踪与completion。不运行源码、测试、模型或CI；本地提交后回交中控，不push、不建实施PR。
- 固定初审f6b653f（内容后保持不变，仅补提交原因为63efd2d28f01632809d63de5411c3a6c33022693）：Standards两项必修——03正式Blocked by/spec依赖表须纳入05、提交须有why正文；Spec PASS，必修0/建议0。两项均已修复，未改变政策或范围。
- 修订`1bed96a4623345652c952226a44b54f516f6c6ae`双轴复核：Standards PASS，原2项必修关闭、剩余必修0/建议0；Spec保持PASS，必修0/建议0。两位均仅只读；此后只回填本记录。
- 最终九份Markdown、76个本地链接/锚点、五票编号/blocked状态/围栏及diff空白检查通过，仓库链接检查通过。以上是文档静态证据，不是实现/运行/真人接受；本地提交后回交。

## 301回交后的兼容差异（2026-10-25，当前补充）

301已由独立PR303回交，本补充回原codex/v05-birthday-dependency-closeout分支，只改本组规划Markdown，不混入303。
完整只读Cross本地727045d76ad84e7b2071410acfb022f2a8a0bc4c原稿（父a3b287c、blob8e0b7e8e）§7：记录operation_id作attempt已认可；修正“已指定quantity即新协议”的误判。现birthday._chosen_items/_plan_items已显式quantity=1，旧显式1/省略1须看后台旧绑定和唯一历史映射；quantity>1或后台新绑定缺身份不降级，来源不明blocked。check捕获也覆盖非冻结ALLOW直交分支，冻结ALLOW仍按旧规则拒绝。
727核对c5959dd，不代表已核对本组d9f8b96的新增05和发布协议；不替Cross提前确认，不选择G1/G2或实施原01—04及新增05。此次仅内容/链接锚点/状态/格式检查，未跑程序、测试、模型或CI，不push、不建PR。
固定补充提交`ddc77b9011bf94e775e2c1057449124934bfdbab`（base d9f8b96）独立复核：Standards PASS，必须项0/建议0；Spec PASS，必须项0/建议0。两位均仅静态只读，核对旧quantity=1、原号身份/原绑定、来源与未授权边界；未运行源码、测试、模型或CI，未改文件。此后仅回填本记录。
最终九份Markdown、76个本地链接/锚点、五票编号与planned/blocked状态、围栏及整段diff空白核对通过，仓库链接检查通过。本地提交回交，不push；301的代码与CI证据保持在独立PR303，未混入本分支。

## 固定896fd7e消费稿后的起始源设计（2026-10-25，当前轮）

基线本地8cdc08f5a8419007b4385374199c2c4306016986；只读完整`896fd7e5d1728b1202818a212ffcb622a658d9b3`（父b2186709）两份原稿：`.scratch/v05-cross-business/birthday-g3-interface-review.md` blob a02f5b6ff08fe7ea4e046da4f71da5cc4a931e03、`issues/08-birthday-quantity-and-unexecuted-revision.md` blob28b8a4b68f85eae7ab5dca71302eb575c7f8592a。原稿不修改，不把§8最小方向接受等同实现或真人决定。
仅本组spec/03/05/对账及本记录：同一窄封存支持无edit/source的首次根、无编辑的普通请求/原运行事件后继与真正编辑；03先预留可信原关联/接受版本/候选，05选完整首份胜者，03同次CAS发布ref/结果/版本/完成投影。明确根不造source/edit、普通缺源不冒充根、取消/异常/发布断点和旧put防覆盖；旧显式quantity=1的后台绑定/唯一历史条件承接8cdc，不按字段存在判升级。
补未来P16/P17验收设计，不新建框架/公开字段/票，不实施01—05，不删完整确认/验证编辑要求或代定G1/G2。不混入PR303、不改任何业务/安全/银行/评测源、Cross票或共享进度。
Erwin最新停止线：材料完成独立双轴审查、本地提交回交后即停；真实E2E由Erwin后续亲自安排，不自动启动S01或三主线真实E2E。已有301及原失败证据保留，本轮不跑源码、测试、模型或CI，不push、不合并/扩用CI例外。
固定受审提交`e2b01e770e04d170e2db36a7f8e142965b7c10ca`（base8cdc08f）：独立Standards PASS，必须项0/建议0；独立Spec PASS（静态设计），必须项0/建议0。两位均核对固定Cross两稿、无前驱根/普通后继/真实编辑及旧单件边界；只静态读取，未运行产品、测试、模型、CI或改文件，审阅后停止。此后仅回填本记录。
最终九份本组Markdown、79个本地链接/锚点、五票编号/围栏与planned/blocked状态，以及整段diff空白检查通过；仓库文档链接检查通过。本地提交回交后停止，不推送、不建实现PR、不启动真实E2E；不将本次静态PASS写成提供能力已实现或新消费确认。
