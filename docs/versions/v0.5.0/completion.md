# v0.5.0 完成情况：系统验收与体验打磨

> 状态：**进行中**（2026-10-21 起，目标 10-30）。
> 口径：按实际交付与证据记录；AI 代行实施与审查不等于真人审查，也不等于 Ringo 安全签核。当前任务与开放问题见[项目跟踪](../../01-项目跟踪.md)。

> 2026-10-27本人新授权：子代理完成除比赛资料外的任务，真实走查保存验收截图；据此恢复必要真实验收，具体[分派与边界](../../../.scratch/v05-control/non-material-closeout-2026-10-27.md)。历史10-25“开发与E2E设计完停”在本轮授权范围内被覆盖，已有失败保留，未定风险政策及真人接受仍分别决定。

> 2026-10-27 核查：新版前台 #318/#319/#320 已按本人指令依次合入，最终代码 `443e9b10`。本地前端 122 项及两种构建通过；真实业务 E2E 与最终接受仍未完成。最新剩余范围见[合入与剩余清单](../../../.scratch/v05-control/frontend-merge-2026-10-27.md)，早期交付表中的当时缺口按后续补记阅读。

## 一、已交付

| 日期 | 交付 | 提交 / 证据 | 边界与未做 |
|---|---|---|---|
| 10-28 | 冻结只读平台与养老金草稿提示合入；个人预算实际采用核对 | #353 `bec56218`、#354 `58ab5158`；[集成持续记录](../../../.scratch/v05-control/integration-2026-10-28.md)、[原个人预算实际批](../../../.scratch/v05-control/adopted-budget-http-2026-10-27.md) | 各自36/10局部通过、两轴0、CI计费未启动；正常预算采用只一次及467/33/占用closed有真实来源。PR341取消两缺口未最终交审，旧组合已中止，不计最终通过；最终backend、页面/截图与真人接受仍待 |
| 10-27 | P01新批实际完成与#349/#350/#351合入 | 主线5278f870；[五批实际HTTP与银行证据](../../../.scratch/v05-control/http-completed-2026-10-27.md)、[后续固定批](../../../.scratch/v05-control/non-material-closeout-2026-10-27.md) | 本人具体批准后显式启用的新P01完成退订、2500储蓄、1000家庭，主账留1500元；三次网关写入与三成功银行记录一致，确认/双因子保留，12维明确演示。原暂停批不覆盖；Cross09实际冻结取消红例、平台23、最终后端、个人预算实际采用及页面/截图仍待 |
| 10-27 | 后续平台/安全/前端与实际闭环记录 | #331—#348（341消费09待最终交审）；[逐票固定批与限制](../../../.scratch/v05-control/non-material-closeout-2026-10-27.md)、[四批真实HTTP证据](../../../.scratch/v05-control/http-completed-2026-10-27.md) | S01原503后完成、重置后再500、生日500/467/33实际成功；P01原暂停保持，21新profile/新批继续。平台445/13skip、来源88、安全656不是整版同源全量；96/B/C实际Failed/Blocked不改名，页面/截图及真人接受仍缺 |
| 10-27 | 非比赛资料初批10项合入；模型/HTTP阶段观察 | #321—#330；[过程及后续快照](../../../.scratch/v05-control/non-material-closeout-2026-10-27.md)、[阶段原始记录](../../../.scratch/v05-control/http-acceptance-2026-10-27.md) | 初阶段500元成功、S01父503；后续见上一行，旧失败不覆盖。API+时钟251与安全599非整版全量，CI计费未启动 |
| 10-27 | 新版对话前台三票全部合入，修正安全暂停恢复提示 | #318 `2a9ebf7e` → #319 `a2386e6b` → #320 `443e9b10`；[完整合入与核查](../../../.scratch/v05-control/frontend-merge-2026-10-27.md)。108/113/122 项阶段验证与构建通过，最终真实 API/契约演示两种构建通过；两轴限定复审 0 必须项 | CI 计费未启动；未新跑后端全量、真实模型/页面/银行 E2E、200%/读屏或真人验收；版本仍进行中 |
| 10-26 | 第四至第七批 8 个 PR 按本人批准合入，并做合入后冒烟 | [合入记录](../../../.scratch/v05-control/merge-batch-04-07-2026-10-25.md)：304=`734c5b7`、303=`57a2fd7`、296=`620746a`、290=`40971d6`、294=`ad401ac`、291=`9a6f756`、300=`5b9b1c3`、305=`5347dd7`；main=`5347dd7`；合入后冒烟 531 节点全过（后端 315=302+13skip、evals 61=57+4 strict xfail、安全 155 passed） | CI 全部计费未启动记 Blocked（按本批本人例外），无远端测试执行证据、0 review；S01 仍 Failed、#290 四 xfail、#291 专项仍 BLOCKED、#305 真实采用/E2E 未跑；共享库迁移、#160、前端页面/200%/读屏、最终安全/体验接受与 Ringo 真人签核均未涉及 |
| 10-25 | 入口修复组合阻塞归因并定向复验（scope_ok） | 组合 worktree `codex/v05-entry-fixes-combination` 本地提交 `7a68a4b`（归因）+`251fad6`（复验）；摘要见[PR收口材料](../../../.scratch/v05-control/pr-closeout-2026-10-25.md) | v1 唯一未归因 `socket.bind` 定位为 urllib3 导入期 IPv6 能力探测（非产品缺陷、未改产品与两PR分支）；分类修正后同并集 214 唯一节点 201 passed/13 skipped/0 阻断/exit 0，节点与逐节点结果与 v1 一致。仍非页面 E2E，不构成 303/304 合入批准 |
| 10-25 | 生日"等待期修改"语义经本人裁定为完整支持 | [本人裁定原文与边界](../../../.scratch/v05-control/birthday-owner-decision.md) | 认可五条共同条件与旧验证码例外（G2-B）；平台01—05/business08 仍未实施、未派工，不批准 PR 合入/CI 例外/共享迁移/前端页面或最终安全体验接受 |
| 10-25 | E2E01—04设计交接完成并停止执行 | 本地217c616，七份规划Markdown、两位独立静态审查0必须项；[本人手工执行交接](../../../.scratch/v05-cross-e2e/manual-execution-handoff.md) | 未运行新代码/测试/模型/浏览器/业务库；生日/异常变体数据与工具仍有缺口，非26条可直接运行。原S01 Failed/PR300保留，不夹带未批代码或附件 |
| 10-25 | 301/302修复分别开发回交，中控核对原始证据 | [303/304接收记录](../../../.scratch/v05-control/entry-fixes-intake.md)：303@cb16311修后13真实路由样本；304@60f0686局部132唯一节点，原JSONL/源码/旧证据与XML/实际退出0核对，两轴必须项清零 | 两PR未合、准确head CI计费Blocked，无新例外；只续派一次必要局部组合核对，不跑真实E2E；路由/局部集成不代页面S01通过 |
| 10-25 | G3提供规划补齐初始与普通状态保护 | 本地21e16ae、六份Markdown、两轴0必须项；[本人具体选择材料](../../../.scratch/v05-control/birthday-owner-decision.md) | 无实现/运行或消费方新签核；01—05/08仍只规划，G1/G2未决定。前端02已中断，另仅续派静态方案收口，视觉和页面批准仍缺 |
| 10-25 | 第三批293→299按本人批准顺序合入，budget business06正式派开发 | 293=`9d6d899`、299=`1b3afec`；[最终head/批准/CI/等价证明](../../../.scratch/v05-control/merge-batch-03.md)。最终backend树与受测c638418相同，沿用133唯一节点及双轴审查 | CI计费未启动，按仅本批例外；共享库未迁移，仅新隔离目录。cross06尚待开发交付；本人随后要求开发与E2E设计完成后停，已通知相关执行线，不自动新实跑 |
| 10-25 | Cross生日G3最终消费核对接收 | 本地896fd7e，独立双轴0必须项/0建议；[§8最终意见](../../../.scratch/v05-cross-business/birthday-g3-interface-review.md#8-对d9f8b96封存提供稿的最终消费意见设计仍blocked)，08补storage05依赖 | 只静态设计；起始/普通状态不可变源及旧quantity=1兼容仍交平台补具体规划，01—05/08未实施，G1/G2仍待本人决定 |
| 10-25 | 单项订阅入口归因与候选完成，302正式派修 | 本地74da8d9，双轴0必须项；中控复算4份产物散列，11唯一Fake测试通过、10行离线观测；[接收/分派](../../../.scratch/v05-control/subscription-diagnosis-intake.md) | 明确停止意图被终态list降级，与301完整目标路由分开；已给subscription单目录实施信号，尚未修复交付，不是新真实模型/银行/页面运行 |
| 10-25 | 生日G3提供条件与消费兼容评议更新 | 平台d9f8b96、Cross727045d，实际双轴及必须项闭合已核对；[G3对账](../../../.scratch/v05-birthday-platform-dependencies/g3-reconciliation.md)新增storage05窄计划票 | 01—05均未实施；精确ID仍可能被共享通道覆盖属于源码推演，非已运行反例。最后消费核对、G1/G2和完整确认/验证编辑仍待，不自动削减范围 |
| 10-25 | 293+299同版本隔离组合与第三批材料完成 | 本地cbf164f、受测c638418，133唯一节点通过/111.49秒，两轴0必须项/建议；中控核对11份产物散列、226源码指纹及7候选文件；[待决定材料](../../../.scratch/v05-control/merge-batch-03.md) | 两PR未合、CI计费Blocked，等待本人仅本批例外；仅新隔离目录，v6旧库回退限制/共享迁移另案。F10仍为业务替身，cross06及真实模型/页面E2E未验收 |
| 10-25 | S01首批真实运行失败，观察器/冻结证据回交PR300 | head31e995e，产品2a070b9；中控核对原JSON、观察器/4附件散列、双轴实际活动及13项局部输出；[接收及Issue301分派](../../../.scratch/v05-control/pr300-s01-failure.md) | 模型1请求/1响应选错单项入口，cross关联0、银行写/操作/效果0；S01 Failed，S02—S05未继续。13项不代E2E通过。PR300未合、CI计费Blocked，无新例外；平台修复/订阅只读归因已派 |
| 10-25 | 预算API02形成PR299并完成中控接收核对 | head d262bb1；最终93唯一节点通过，双轴0必须项，中控解析XML/散列并确认运行树一致；[接收记录](../../../.scratch/v05-control/pr299-intake.md) | Draft未合入、CI计费Blocked，未获新例外；预算业务/规划替身不代真实采用/E2E。293+299隔离定向组合已续派，cross06尚未开工 |
| 10-25 | 生日平台及Cross消费方规划回交 | 平台c5959dd的[两选项](../../../.scratch/v05-birthday-platform-dependencies/decision.md)、Cross e4cb7b7的[G3评议](../../../.scratch/v05-cross-business/birthday-g3-interface-review.md)；实际双轴活动核对，检查点发布P2修订复审通过 | 仅文档，G3发布边界/原号兼容继续对齐，G1/G2未裁定；完整确认/验证编辑需求未删除，未实施或运行模型/测试 |
| 10-25 | 第二批五PR按Erwin批准全部合入，预算API02与真实减支E2E01开工 | #298=`6ce7fb0`、#284=`4d9bd57`、#292=`e402bc4`、#295=`3239fd7`、#297=`2a070b9`；[最终head/批准/CI及等价核对](../../../.scratch/v05-control/merge-batch-02.md)。主线运行树与受测0aed529一致，沿用156唯一节点和独立双轴 | CI计费未启动，按仅本批本人例外；API02新实现、真实E2E结果尚未最终回交。其他PR/数据库升级/#160/最终接受未纳入批准 |
| 10-25 | 生日G2安全设计评议回交 | 本地bce306d、[具体问题与待决定建议](../../../.scratch/v05-birthday-security-review/review.md)，双轴修订后0必须项 | 源码推演、未实施或运行；旧授权/验证码/历史/审计边界仍需设计收口，本人未裁定G2-A/B/C，平台/Cross正在材料协同 |
| 10-25 | Erwin批准第二批五项及本批CI计费例外；生日平台依赖规划回交 | [第二批批准记录](../../../.scratch/v05-control/merge-batch-02.md)；平台本地f481f4b、[规格/四票](../../../.scratch/v05-birthday-platform-dependencies/spec.md)及双轴复审0必须项 | 五项按顺序同步核对中，批准不代记合入；平台四票仅规划，G1契约/G2本人安全/G3跨模块接口待收口，未实施或运行测试 |
| 10-25 | 生日数量与未执行调整缺口核查及business/08拆票 | 源提交1d7f1fa；[缺口/最小规格](../../../.scratch/v05-cross-business/birthday-quantity-gap.md)、[08计划票](../../../.scratch/v05-cross-business/issues/08-birthday-quantity-and-unexecuted-revision.md)、[独立审查](../../../.scratch/v05-cross-business/birthday-quantity-design-review.md)；两项规格必须项已修订，两轴复审清零 | 仅静态核查与Q01—Q10框架，未运行复现/测试/模型，未实施；平台提供方核查/拆票已续派，确认失效/执行项身份及06预算前置未闭合，页面与E2E未完成 |
| 10-25 | 第二批五项同版本定向核对完成 | main608255f + #298/#284/#292/#295/#297，受测0aed529、材料37fb62f；156唯一节点通过、双轴0必须项；[合入材料](../../../.scratch/v05-control/merge-batch-02.md) | 待Erwin本批合入/CI例外批准，尚未合入；养老金资金仍暂停，API02/真实模型/页面E2E未完成 |
| 10-25 | 五项支撑组合与只读合入材料回交 | 本地664c88b：#293/#296/#298/#294/#291同树160通过、两轴0必须项；只读材料078d89c、293补充1aca3ae分别经两轴复核，中控核对现有XML/哈希及293历史工具摘录 | 不是整版全量或预算真实接线；293原1607仅有历史工具输出、无当批独立JUnit/日志，v6回退限制待后续裁定；银行四xfail/B26和最终接受保留 |
| 10-25 | 可信F10来源平台01完整后端回归通过 | PR298受测 `4f18247`：1752通过/0失败/0错误/0跳过，764.59秒；最终 `5ebc133`仅补证据，中控核对原始JUnit/退出码及哈希 | Draft未合入、CI计费Blocked，无本批例外；五项支撑组合另行定向核对，API02/cross06/真实采用及页面E2E尚未完成 |
| 10-25 | 养老金07主线冲突整理回交 | PR297 `9e25a8f`；生日/养老金相关定向70通过、Spec独立2通过，两轴0必须项 | Draft未合入；生日与养老金能力同时保留，最新四PR组合已续派但未回交；不是模型/页面E2E |
| 10-25 | 订单来源门组合回归完成 | PR294 `6204e14`依赖PR296 `b41ef64`；[实际证据](https://github.com/DrErwin/hackerthon-bank-agent/blob/6204e14b3f5e3ac5fd87dae5796b7580fe40ee77/evals/mockbank/round-attribution.md)：53通过、4 strict xfail，双轴无剩余必须项 | 两PR未合入；上游旧订单拒绝且合法订单仅付款一次，裸银行四项边界与B26仍保留，原银行专项/页面E2E/真人接受未关闭 |
| 10-25 | 账单组合恢复503有效完整诊断批回交 | 固定backend `6f0a56d`、本地材料 `9e3d13d`；1606通过/0失败/0错误/0跳过，双轴0必须项；[诊断检查点](../../../.scratch/v05-control/recovery-503-checkpoint.md) | 原503未复现、根因仍未定；旧失败与观察受扰批保留。不是最新main四项组合或模型/页面E2E通过，未新增合入批准 |
| 10-25 | 可信F10采用来源平台01形成PR298 | head `4f18247`，定向87通过；两轴独立各35通过、0必须项；[来源平台票](../../../.scratch/v05-budget-adoption-origin/issues/01-platform-origin.md) | Draft未合入，完整后端回归进行中；API02、预算业务接入与采用E2E未做，不等于授权动钱 |
| 10-25 | 第一批五PR经Erwin批准合入，生日页面02续派 | #270 `b1382c2`、#285 `7edb7b0`、#287 `421b344`、#289 `31e9f27`、#288 `3b865b0`；[逐项验证与精确head](../../../.scratch/v05-control/merge-batch-01.md) | 96样例仍NOT_RUN；CI计费Blocked按本人批准例外处理；Issue215/271按各自范围关闭，216/227与最终安全/体验接受未关闭；前端02仅启动走查准备，E2E未做 |
| 10-25 | 订单来源平台14回交；F10采用来源设计与拆分确认 | PR296 `296f2eb`：后端1599、银行14、定向13，双轴PASS；[F10来源设计](../../../.scratch/v05-budget-adoption-origin/spec.md)两轴0必须项 | 296未合入；来源平台01已委派、API02等前置，尚无实际采用或E2E证据；503原失败继续保留 |
| 10-25 | Erwin批准第一批五PR及CI计费例外 | [批准范围与合入记录](../../../.scratch/v05-control/merge-batch-01.md)：270/285/287/288/289 | 正在刷新主线与复验，不代记已合入；#160仍讨论，未选择政策；最终安全/体验接受不变 |
| 10-25 | 预算业务06设计与安全后端评测修正回交 | [预算设计审查](../../../.scratch/v05-cross-business/budget-design-review.md)；PR291 `f197601`：安全目录155通过、两轴复审无必须项 | 预算仅设计，可信F10来源前置未实现；安全PR未合入，页面专项未完成；账单组合恢复503继续诊断 |
| 10-25 | 已采用预算存储代码回交（待合入） | PR #293 `7c2fe00`；后端1607、本票19、银行14；双轴审查0必须项 | 仍Draft、CI账户阻塞；应用库v6回退限制保留；未合入、未迁移共享库，cross接入与生日预算E2E未做 |
| 10-25 | 包05准备文档与首批委派回交 | [运行准备](../../../evals/cross/runbook.md)、[双轴审查](../../../.scratch/v05-cross-e2e/review.md)；#284/#285/#287/#288/#290待合并，#289收尾 | 仅准备及待合并交付；银行专项4项跨轮次未满足、取消未知后继续下单P1复核中；真实E2E与真人接受仍未完成 |
| 10-25 | 联动页面票01与平台11代码合入 | PR #281 `4bba921`、PR #283 `e9517b8`；后者提交报告前端79 passed与build通过，中控未重跑 | 页面真实E2E、200%缩放与读屏未完成；不代表包04/05验收通过 |
| 10-25 | 中控分派7个执行对话，包05/06启动 | [中控调度表](../../../.scratch/v05-control/dispatch-2026-10-25.md)；均为GPT-6.1-sol/high，要求交付后子代理审查 | 仅分派与启动确认；原对话随后合入PR #281/#283（见当前状态），新增委派工作尚未形成验收证据；真人接受未发生 |
| 10-25 | 包 04 领取与两票细化 | Erwin 本人指令；[工作规格](../../../.scratch/v05-cross-frontend/spec.md)与其两票 | 页面走查、代码、联调和 E2E 未开始；执行交其他对话，未代领包 05/06 |
| 10-24 | 安全包 02 领取、规格与两票细化 | Erwin 本人领取；[规格](../../../.scratch/v05-cross-security/spec.md)、[两票交接](../../../.scratch/v05-cross-security/handoff.md) | 01 可准备规则与接入方案，代码待执行对话；02 实跑等平台 09/前端 02，未运行安全专项或代签本人审查 |
| 10-24 | v0.5 全阶段执行责任调整 | [项目跟踪](../../01-项目跟踪.md)及六包/相关票负责人同步为 Erwin；下一步建议安全包 02 的票 01 | 仅更新责任与建议；既有验收证据不变，未开工的包不计开始或完成 |
| 10-24 | **包 03 票 01 合入、票 02 审查通过待合入**：票 01 PR [#269](https://github.com/DrErwin/hackerthon-bank-agent/pull/269)（squash 7609976，CI 绿，子代理审查 PASS-with-notes）；票 02 PR [#268](https://github.com/DrErwin/hackerthon-bank-agent/pull/268)初轮审查四项 major（逐笔刷新未生效/重试死循环/失败不暂停/退订依赖未实现）全部修复，复审 PASS-with-notes 且 N1/N2 小修完成，本地 81 passed | CI 因 GitHub 账户计费问题未跑成（非代码原因），待恢复后合入 #268；票 03 生日阻塞于安全 01（未实施）；账单入口类型化输入缺口交账单负责人；装配/E2E/签核未做 |
| 10-24 | **包 03 三票全部实施合入**：票 02 养老金 PR [#268](https://github.com/DrErwin/hackerthon-bank-agent/pull/268)（初轮审查四项 major 全修复，复审 PASS-with-notes，squash 9d4386e）；票 03 生日编排及预算约束 PR [#274](https://github.com/DrErwin/hackerthon-bank-agent/pull/274)（前置安全 01 #272 与平台 10 #273 合入后实施；初轮审查 B1/B2 两个资金安全 blocker 修复+复审 PASS-with-notes+N1/N2 必修项，squash 4a5d25c）。冻结=采用预算上限、§3.5 限定释放条款与授权、订单/付款分离、各阶段未知沿原编号回查、用户+月份共享预算经串行占用接缝、D1 冲突核对 | CI 因 GitHub 账户计费故障全局未跑成（按 #272/#273 口径凭本地全量证据合入：cross 43 + subscription 56）；生日真实安全门/网关装配属平台 09（birthday_ports 已交付）；CrossStartInput 预算引用/改版接线、账单入口类型化输入缺口、包 05 E2E、真人签核未做 |
| 10-24 | **联动 G1 闭合与包 03 业务两票实施** | 平台输入核对 PR [#264](https://github.com/DrErwin/hackerthon-bank-agent/pull/264)、订阅类型化入口 PR [#266](https://github.com/DrErwin/hackerthon-bank-agent/pull/266)（均 CI 绿、子代理审查通过后合入）；票 01 减支编排+共用计划骨架 PR [#269](https://github.com/DrErwin/hackerthon-bank-agent/pull/269)、票 02 养老金安排与留存核算 PR [#268](https://github.com/DrErwin/hackerthon-bank-agent/pull/268) 已实现，cross 目录测试 21 项全绿，审查进行中 | 账单入口类型化输入缺口交账单负责人；票 03 生日阻塞于 Ringo 安全 01（planned）；平台 05/09 装配、前端、包 05 E2E 与真人签核未做 |
| 10-24 | 联动包 03/05 阶段转派、03 接包与三票细化 | Erwin 本人确认；[包 03 规格](../../../.scratch/v05-cross-business/spec.md)及[交接](../../../.scratch/v05-cross-business/handoff.md) | 05 尚未领取；G1 输入支持及安全/票面前置未闭合；未写业务代码或运行 E2E |
| 10-24 | **平台票 09 生日真实装配+微票 04×2**（v05-cross-platform/09、v05-cross-business/04、v05-cross-security/04） | PR [#277](https://github.com/DrErwin/hackerthon-bank-agent/pull/277)/[#278](https://github.com/DrErwin/hackerthon-bank-agent/pull/278)/[#279](https://github.com/DrErwin/hackerthon-bank-agent/pull/279)：step-up 验证接缝、顺序确认放行、birthday_runtime 真实 ports（安全门/双因子/live-claim/限定释放全链）；全链测试真实账实核对（含停止场景 D2 部分完成与限定释放） | B28 故障配置未装配（未知回查全链归 E2E）；chat 链未端到端；三主线 E2E/前端/真人签核未做 |
| 10-24 | **平台票 05 装配+安全微票 03**（v05-cross-platform/05、v05-cross-security/03） | PR [#275](https://github.com/DrErwin/hackerthon-bank-agent/pull/275)/[#276](https://github.com/DrErwin/hackerthon-bank-agent/pull/276)：cross 白名单冻结快照；真实组合挂载 cross（自然目标路由、生日受阻不伪装、养老金入口、原转账回归、读阶段零银行写入）；期间 #268/#269/#272/#273 由他人合入 | 票 09 仅剩生日编排（cross-business/03）前置；GitHub Actions 账户计费阻塞（组织已知），本地全量兜底；E2E 未开始 |
| 10-24 | **联动平台底座七票实施**（v05-cross-platform 01/02/03/04/06/07/08） | PR [#256](https://github.com/DrErwin/hackerthon-bank-agent/pull/256)/[#257](https://github.com/DrErwin/hackerthon-bank-agent/pull/257)/[#258](https://github.com/DrErwin/hackerthon-bank-agent/pull/258)/[#259](https://github.com/DrErwin/hackerthon-bank-agent/pull/259)/[#260](https://github.com/DrErwin/hackerthon-bank-agent/pull/260)+[#261](https://github.com/DrErwin/hackerthon-bank-agent/pull/261)/[#262](https://github.com/DrErwin/hackerthon-bank-agent/pull/262)/[#263](https://github.com/DrErwin/hackerthon-bank-agent/pull/263)（均 CI 绿）。公共模型+契约 §5.4 修订；应用库 v5（父子关系/D1 资金安排原子接缝/预算占用串行/受控资料）；受控子任务派发与恢复+D1 普通转账提交前暂停（银行零写入）；通用 children 端点；银行库 v4 原子对象+核销流水对手方回填；B10—B13/B20—B22 服务与网关默认拒绝写入+响应丢失故障；F36 配送受控录入。每票子代理审查（发现的 2 个必须项均已修复复测）+票面回交 | 票 05/09 阻塞于 v05-cross-business（未代写）；D1 错误呈现 source/field 偏差待转账负责人适配；Ringo 安全审查、前端接入、E2E、真人签核未做；合入前后端全量 1469 passed |
| 10-24 | 联动后续工作交接 | [执行交接](../../../.scratch/v05-cross-platform/handoff.md)：补齐票一收口步骤、九票顺序、跨包开始条件、决策分工及可转交指令 | 交接文档已准备；未代执行者接票，未实施代码或运行 E2E |
| 10-24 | 联动票 01 约定裁定材料 | [裁定稿](../../../.scratch/v05-cross-platform/01-decision.md)、[字段与样例](../../../.scratch/v05-cross-platform/01-contract-detail.md)；源码核对确认复用部分完成状态及配送 F36 | Erwin 已确认 D1/D2 业务规则，具体契约及必要安全确认仍待完成；未实现公共模型、未运行模型测试/E2E，不代表开发票完成 |
| 10-24 | 第一个联动包接包与九票细化 | Erwin 本人明确接受；[执行交接](../../../.scratch/v05-cross-platform/handoff.md)与九票增加输入输出、边界及验证步骤 | 公共约定/安全审阅待确认；具体执行者由 Erwin 指派；代码和 E2E 未启动 |
| 10-24 | 联动共享规格、六包及 21 张规划票 | [规格](../../../.scratch/v05-cross-linkage/spec.md)、[公共约定方案](../../../.scratch/v05-cross-linkage/contract-proposal.md)、[正式票索引](../../../.scratch/v05-cross-linkage/ticket-proposal.md)；PM 已批准顺序和拆分 | 公共约定细节/安全审阅仍待完成；各负责人未代领，代码与 E2E 未开始 |
| 10-24 | 跨场景联动 PRD 重写（需求文档） | [PRD](../../prd/06-跨场景联动-PRD-2026-09-23.md)、[E2E 用例设计](../../../evals/cross/representative-cases.md)；PM 已确认三个生活场景，补齐 AI / Harness / 确定性业务边界 | 新增公共约定待收口；实施未开工、未拆票、未运行联动 E2E，不代表功能交付或安全签核 |
| 10-21 | 管理端审计导出 F35 / F24 audit 分支（[#214](https://github.com/DrErwin/hackerthon-bank-agent/pull/214)） | `b01ceb9`；E2E 117 passed、后端全量 1191 passed、真实演示库 3636 事件证据包 | 管理前端入口按 PM 决定未做（已知限制） |
| 10-22 | 可信观察接缝与四项体验能力（[#216](https://github.com/DrErwin/hackerthon-bank-agent/issues/216)，[交付记录](../../../evals/security/observers-2026-10-22.md)） | 九票合入；离线 E2E 26 checked / 0 failed、真实模型 GLM Coding Plan 6 次调用全 Passed | 前端粘贴框与记忆管理页未做（须 PM 同意另开前端票）、生产检测器 #160 未做、真实页面粘贴走查与批次 B/C 全量未做 |
| 10-22 | 演示 E2E 修复与卡片版式（#228–#252，[逐票进度](../../../.scratch/bank-e2e-remediation/progress.md)） | 真实三条演示路径、银行计数、56 条独立分类探针；前端 59 项测试、build、CI 与 AI 双轴代审通过 | 真实 200% 缩放、用户最终体验验收未做；Issue #227 保持开放 |
| 10-23 | 连续办理体验（[#253](https://github.com/DrErwin/hackerthon-bank-agent/pull/253)） | `b7fdd91`；可选资料、中途查询、明确反馈、结果刷新；真实模型 + HTTP + 隔离模拟银行走通转账全链路 | 200%/读屏未重跑；AI 双轴代审，非真人、非 Ringo 签核 |
| 10-23 | 连续退订与业务 E2E 修复（[#254](https://github.com/DrErwin/hackerthon-bank-agent/pull/254)） | `0e34351`；验证复用、断线补读、账单刷新保留范围、可读失败原因；后端 1431 passed、前端 70 passed | 同上 |
| 10-22～10-23 | **订阅场景前端插槽**（清单/退订/回执/刷新） | #230–#232、#247、#253/#254；真实页面取消优酷（专用验证 + 银行成功）、连续退订优酷→网盘、清单自动刷新至 0 项 0 元 | 卡片未单独标「7 天内会扣款」角标（回复文案已含）；200%/读屏属全局缺口 |

本阶段分工：2026-10-24 PM 明确“这个阶段，所有的事情都由我自己完成”：v0.5 剩余执行工作统一由 Erwin 承担，含六个联动包、#160 检测器装配、#215 样例扩充、适老化检查、集成修复和验收。安全规则审阅也由 Erwin 本阶段代行，不再等待原负责人接包。每票仍按目录独立实现、审查和交付；AI 审查、自动化测试、Erwin 本人审查/接受及历史 Ringo 专业签核分开记录。期限至 v0.5 收口，交接接口、证据与遗留后，后续阶段重新分派。

## 二、未完成（v0.5 剩余）

| 事项 | 负责人 | 状态 |
|---|---|---|
| 跨场景联动：真实业务验收及已知恢复缺口 | Erwin（全部工作线） | [新实际批](../../../.scratch/v05-control/http-completed-2026-10-27.md)证明S01原503后完成、整体重置后再次500、生日500冻结/467付款/33释放；P01原暂停保留，21限定profile与新批执行中。Cross09最后交审、最终全backend、个人预算实际采用和26变体页面继续；10-25原Failed未覆盖，真人安全/体验接受未完成 |
| 生产检测器装配（[#160](https://github.com/DrErwin/hackerthon-bank-agent/issues/160)） | Erwin | 有限真实危险话术检查已存在，普通低中风险仍依赖流程夹具；去夹具/未知处置待裁定，不能概括为完全没有接线；Erwin正讨论自然多样输入目标 |
| 200% 缩放、完整读屏、真机软键盘 | Erwin | 未做 |
| 本阶段本人安全审查与接受 | Erwin（本阶段代行） | 待本人按实际证据审查；历史 Ringo 专业签核仍缺，不改写 v0.4 例外或代签 Ringo |
| 用户最终体验验收（#227） | PM | 待做 |

## 三、验收标准进度

1. **既有业务与三个联动目标的正常及关键异常 E2E**：转账、账单、订阅已有 v0.4 历史验证（含例外）；联动与新版页面代码已合入，10-26 部分真实页面路径有证据，但转账风险暂停、生日止于方案核对，三目标完整正常/关键异常 E2E 尚未完成，**本条未达成**。
2. **安全评测证明确认、权限、注入防御和隐私边界**：离线全量 20 Passed / 0 Failed / 337 Blocked、真实模型批次 A 24 轮、页面回归 24/24 已有证据；批次 B/C 解门验证与安全侧真人复核仍缺，**部分达成**。
3. **演示环境可重置、结果可重复**：本机演示库可重置，证据按票归档；尚未形成独立的"可重置 + 可重复"验收记录，**部分达成**。
4. **已知限制和遗留问题有明确记录**：v0.4 例外 E1—E10 与本页剩余项均已登记，**达成**。

## 四、启动条件

- [x] v0.4 三场景与完整安全能力完成（2026-10-22 联合验收，含例外）。
- [x] 各负责人提交评测与已知问题（转账/账单/订阅/安全及联动已有实现和局部证据；三目标完整真实 E2E 仍待）。

## 五、验证状态

- 2026-10-26（银行跨轮次对象边界收口，main `5b4b99d`）：[v05-bank-round-objects/01](../../../.scratch/v05-bank-round-objects/issues/01-object-round-storage.md) `819bbfb`（银行库 v5：冻结/订单对象轮次归属；v4 有对象行明确拒绝加载）、02 `b63ec1b`（服务层按可信轮次校验，跨轮 `ACCESS_DENIED`、启动拒绝无轮次对象行）、[评测 02](../../../.scratch/v05-cross-bank-eval/issues/02-round-object-regression.md) `5b4b99d`（四项 strict xfail 转正 + 混合订单轮次用例）合入。隔离实跑：生日单文件 **42 passed**、归因 **3 passed**、记录合跑 **217 passed / 0 xfailed**、旧 CI 评测 **14 passed**、平台/安全定向 **46 passed**；合入后 main 全后端 **2121 passed / 13 skipped**（18:33）。CI 仍因账号计费未启动记 Blocked；页面/模型/HTTP E2E、B26 重置、PM 体验与专业安全签核未做，不代签。
- 2026-10-26（第四至第七批合入后，main `5347dd7`）：后端受影响定向并集 **315 节点 / 302 passed / 13 skipped / 0 failed**；evals 证据侧 **61 节点 / 57 passed / 4 strict xfail / 0 failed**；`evals/security` **155 passed / 0 failed**。批次 5 与批次 7 另在各自实际落点树上复跑（57 节点与 cross 93 passed）。本轮不是全后端、不是页面/模型/银行 E2E。
- 2026-10-24（联动平台底座七票）：分票验证——contracts 81、storage 38（应用库 31+银行库 38 分列计 37+新增）、agent_platform 238、api 175、services 59 passed；#258 合入前后端全量 `1460 passed`、#260/#262 期间全量 `1469 passed`；PR #256—#263 CI 全绿。
- 2026-10-23（#254 rebase 后、推送前）：后端 `1431 passed / 0 failed`、mockbank `14 passed`、前端 `70 passed`、`npm run build` 通过、链接与空白检查通过；#253/#254 的 PR CI 与 main 推送 CI 均绿。
- 本轮验证为 AI 代行执行与整理，**不是真人审查、不是 Ringo 专业安全签核**；用户最终体验验收与 200% 缩放/读屏未做。

## 六、生日功能（v0.5）后端交付（2026-10-26）

- 八票全部合入：01 [#306](https://github.com/DrErwin/hackerthon-bank-agent/pull/306) `e14f30d`、05 [#307](https://github.com/DrErwin/hackerthon-bank-agent/pull/307) `5863340`、06 [#308](https://github.com/DrErwin/hackerthon-bank-agent/pull/308) `d62d01d`、02 [#309](https://github.com/DrErwin/hackerthon-bank-agent/pull/309) `78163a1`、03 [#310](https://github.com/DrErwin/hackerthon-bank-agent/pull/310) `d5c069c`、04 [#311](https://github.com/DrErwin/hackerthon-bank-agent/pull/311) `d0e3b1e`、08 [#312](https://github.com/DrErwin/hackerthon-bank-agent/pull/312) `2d9cfe2`、09 [#313](https://github.com/DrErwin/hackerthon-bank-agent/pull/313) `6a6526e`。每票单目录、单 PR，两位独立子代理规范轴+规格轴审查、必须项闭合；AI 审查不等于本人或 Ringo 签核。
- 合入后本地实测（main `6a6526e`）：`agent_platform` **376 passed / 13 skipped**、`modules/cross` **120 passed**、`api/test_app.py` **85 passed**。2026-10-26 在 main `dedaf9b` 上做合并态复跑：`app/agent_platform` + `app/modules/cross` + `app/api` **721 passed / 13 skipped / 0 failed**（13:56）。CI 因账户计费未启动，**不记 CI 绿**；这不是全后端、不是页面/模型/银行 E2E。
- 能力与缺口见 [生日可交付事实与交接缺口](../../../.scratch/v05-birthday-platform-dependencies/delivery-handoff.md)。
- **仍未完成**：真实 E2E、200%/读屏/真机、最终安全与体验接受；页面走查与前端02已由下条补记交付。已知缺口：G3 跨会话恢复接线、普通输入发布断点的 API 自动恢复、旧任务/legacy 编辑 `SOURCE_UNAVAILABLE`、安全语义扩展（`get_retirement` 复用闸门）待本人确认。

- **2026-10-26 补记（前端票 02 合入）**：本人当日页面走查通过（D01—D11）并批准 6 条补充文案后，前端 02 [PR #314](https://github.com/DrErwin/hackerthon-bank-agent/pull/314) squash `4d2201a` 合入：确认/验证卡渲染后端发布选项并走 F10、错误 reason 分档、生日结构化收尾、受控配送专用表单（原文只进请求体、引用只留内存、刷新回表单）、已批准文案逐字落地。前端 `npm test` **103 passed / 11 files**、`npm run build` 通过。生日九票（后端八票 + 前端 02）至此全部合入。**仍未做**：真实页面/模型/银行 E2E、视觉、键盘、200% 缩放、读屏、最终安全与体验接受。
