# 周恩宇 v0.4 账单实施台账


## 2026-10-21 · 当前最新核查（覆盖后续旧时间线；AI执行记录，非Erwin/Ringo签核）

个人10票状态：**01/02/03/04/05/08/09/10 已有合入交付证据**；**06/07 in_progress（分阶段评测，不得记完整通过）**。新增 Issue #188 已随 PR #197 关闭。账号 `zhouey314-cloud` 个人已关闭的 #197/#198 不再占用两张未合 PR 名额。

| 工作 | 2026-10-21 GitHub事实 | 未完及签核边界 |
|---|---|---|
| L01 / L02 / L03 与模块返修 | #92/#131/#140/#151/#171/#182/#183 已合；L02安全业务同步 #197、安全冻结白名单 #196、平台注册 #192 全部合入，Issue #187/#188/#190 closed | 真实模型、浏览器、专业安全属相应独立工作线/联合验收，不由本模块代签 |
| 票06 公共业务评测 | #198 **已合入 main**，17个L01公共业务场景原始专项 [Actions #39425788637](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/39425788637) 17/17成功；新主线复跑另见 main 对应报告 | **仍欠每功能≥10、每异常≥3以及L02/L03完整公共业务证据**；保持 `in_progress`，不能把96条设计当作执行数 |
| 票07 HTTP与联调 | 7条L03/F21–F24真实in-process HTTP场景、87请求，固定旧源专项 [Actions #39426333629](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/39426333629) 7/7；此前分支重基后，新提交 [PR #208](https://github.com/DrErwin/hackerthon-bank-agent/pull/208) 已送Erwin审核 | **新main尚无票07独立专项复跑记录**；旧源的7/7不能充作新head测试；L01/L02 HTTP、SSE/恢复/故障分支、真实模型/React交叉证据与安全专业签核仍要分层验收 |
| 其他工作线进展 | 前端账单插槽 #199、主入口替换 #201 已合入；前端真实GLM+浏览器证据已由前端线独立存档；安全/平台 L02前置已合 | [Issue #123](https://github.com/DrErwin/hackerthon-bank-agent/issues/123) 平台纵向联合验收仍由Erwin负责且未关闭；Ringo本人安全批准不能由AI测试代签 |

本轮只更新本人过程文档，不擅自合并代码PR、不将阶段1 `Passed` 转为整包 `accepted`。后文2026-10-20及更早段落为当时快照，已不代表当前GitHub状态。


## 2026-10-20 21:00 · Ethan 最新可验收状态

**按10张实施票**：01/02/03/04/05/08/09/10 属于已合并、模块/黄金子范围 resolved；06/07 属于在 GitHub 真实新主线实跑但整体业务/联调数量未达标的 `in_progress`。另外 [Issue #188](https://github.com/DrErwin/hackerthon-bank-agent/issues/188) 是 10-20 临时新增的 L02 安全准入业务联动票，不应被遗漏。**项目 v0.4 仍在联合验收 `planned/in_progress`，绝非 accepted。**

| 项目/个人事项 | 最新可核实证据 | 还差什么 |
|---|---|---|
| 01/03/08 L01 统计/公开读账/返修 | PR #92/#131/#140 合并；Erwin L01 真实 GLM/银行阶段一已有独立验收 | BF 整包票06/07另验 |
| 02 旧算术评测 | PR #93 合并，147=130算术+17工具，原始gzip与动作链验收 | 不能把96设计当成96业务通过 |
| 04 L02 模块 | PR #183 合并；模块与原任务/异常四规则均有回归 | 平台 #190 [PR #192](https://github.com/DrErwin/hackerthon-bank-agent/pull/192)和安全 #187 [PR #196](https://github.com/DrErwin/hackerthon-bank-agent/pull/196) 未合，真实L02未完 |
| 05 L03 报告 | PR #151 合并、Erwin 平台阶段二 [PR #193](https://github.com/DrErwin/hackerthon-bank-agent/pull/193) 合并；真实glm-5.3两次+ F21/F22/F24 | 前端浏览器/联合验收与真人安全签核不在模块票内 |
| 09/10 返修 | PR #182/#171 合并，Issue #136/#145 CLOSED，账单防重及审计持久化修复有实测 | 历史审计数据清理属 Erwin/Ringo |
| 新 Issue #188 安全准入切换 | [PR #197](https://github.com/DrErwin/hackerthon-bank-agent/pull/197) 最新版本 `8a8de42` 仅修改业务测试，支持v2拒绝/v3合法放行、漂移/越权拒绝；[CI #39427486208](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/39427486208) **996 backend+14 MockBank** 成功 | **等待Erwin合PR#197、Ringo重基并合安全PR#196、平台PR#192审合**，Issue仍OPEN |
| 06 完整业务评测（阶段一） | [PR #198](https://github.com/DrErwin/hackerthon-bank-agent/pull/198) 源 `c2e8f3e` 17/17公共L01通过，[专项 #39425788637](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/39425788637)，新gz+SHA256归档；[PR CI #39426994398](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/39426994398) **967 backend+14 MockBank** | 仍缺 L02/L03等每功能≥10、每类异常≥3的完整公共业务样本，尚不能结票 |
| 07 HTTP/前端协同（阶段一） | 最新 [分支 `test/bills/07-http-l03-20261020`](https://github.com/DrErwin/hackerthon-bank-agent/tree/test/bills/07-http-l03-20261020) 源 `e111183` 7/7HTTP场景、87请求，[专项 #39426333629](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/39426333629)，新gzip/哈希已归档 | 未开PR（本人当前两张未合PR #197/#198已满），剩余完整L01/L02 HTTP、React与安全签核另验 |

**个人交付真实进度**：所有既有核心模块 PR 均已合并；#188新回归和#06一期已提审、CI全绿，#07本期最新源码与gzip在远端分支待PR名额；不能声称01—10以及#188全部“验收完成”，也不能由Ethan代签平台/安全/前端工作线。以下旧状态为历史发生时快照，请以上表为准。


## 2026-10-20 最新正式收口记录

- **已合入 main**：PR #92（统计内核）、#131（L01）、#140（L01返修）、#151（L03报告）、#93（147项算术/工具评测）、#171（读取审计修复）；Issue #145 已关闭。GitHub PR/Issue 是唯一正式状态来源。
- **正式已提审但未合入**：[PR #182](https://github.com/DrErwin/hackerthon-bank-agent/pull/182)（票09/#136模块防重；[CI #39348638637](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/39348638637) success：850 后端+14 MockBank）和 [PR #183](https://github.com/DrErwin/hackerthon-bank-agent/pull/183)（票04/L02异常识别；[CI #39348872148](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/39348872148) success：942 后端+14 MockBank）。两 PR 均已请求 Erwin review。Issue #136 仍开放，需 #182 审查合并后关闭。
- **票06/07评测证据**：票06分支 `test/bills/public-business-evidence-06` 已保存 17/17 L01 业务路径证据；票07分支 `test/bills/report-http-evidence-07` 及独立 [Actions #39278072579](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/39278072579) 已 success，验证 7 个 HTTP 场景，但这两票仍是**阶段性**，不能等同每功能≥10/每异常≥3、BF01–BF07全部通过。仍因最多同时 2 张 PR 限制待顺序提审/补完整覆盖。
- **平台/安全/前端联合验收**：L02/L03 生产工厂、正式安全声明、真实模型+React 插槽、F21–F24 真实纵向链路仍由 Erwin、Ringo、前端线按各自实施票审批/联调；Ethan 提供接口/测例，不代签专业结论。
- **本人的当前交付状态**：主要账单模块与修复开发已推送并有测试记录；不代表个人全部任务 `resolved`，也不代表团队 v0.4 整包 `accepted`。


## 2026-10-19 23:35 · 最后验收交接（优先于下文历史记录）

| Ethan 事项 | 已完成、固定提交与独立证据 | 尚不能宣告完成的流程 |
|---|---|---|
| L01/既有返修 | #92、#131、#140 已合入，平台阶段一真实 GLM/MockBank 受控账单统计路径验收记录可查 | BF01—BF07 全链路另验 |
| L03 报告（票05模块部分） | [#151](https://github.com/DrErwin/hackerthon-bank-agent/pull/151) 已被 Erwin squash 合入 `40a61c32e64c34f4b3872576f05a3d7fc3ee8cc7`，主线 CI [39271097627](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/39271097627) 782 backend +14 MockBank passed | 生产 L03 注册、读权限安全声明、F21—F24、React 仍要各 Owner 联调 |
| 02 / #93 算术及工具评测 | [PR #93](https://github.com/DrErwin/hackerthon-bank-agent/pull/93) head `1669bada8c3ce19ef120c1ec3ad9abab1c6c50e7`，已在**含 #151** 的源码 `49ce93a0353dcac5923e329d240eff7c7963373f` [实跑 147/147](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/39274554945)（130算术+17工具），原始 gz+SHA256 已入库；最新 [CI 39275035533](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/39275035533) 782+14 passed | **PR open，等 Erwin 审查并合并**；不是 96 个业务设计全部实跑 |
| 10 / #145 读取审计修复 | [PR #171](https://github.com/DrErwin/hackerthon-bank-agent/pull/171) head `b3a00b004ca5998eb82e651543bd6d9d89a5ab27`，新 [CI 39272661635](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/39272661635) 784 backend+14 MockBank passed，已请求 Erwin/Ringo | 安全审核、squash 和 Issue #145 关闭由负责方；历史敏感审计处理不在该 PR 之内 |
| 04 / L02 异常核对 | 已将 L02 与已合入的 L03 manifest 和 README 无损合并，分支 [`7d9682a`](https://github.com/DrErwin/hackerthon-bank-agent/tree/feat/bills/l02-private-rules)，独立 [CI 39276005890](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/39276005890)：308 bills +887 backend +14 MockBank passed | 尚未开单目录 PR、未合并、未生产注册；等本人 2 PR 上限释放 |
| 09 / #136 模块防重 | 分支 [`6bbd921`](https://github.com/DrErwin/hackerthon-bank-agent/tree/test/bills/l01-module-dedup-136-09) 保留 L03 代码和文档，独立 [CI 39276005890](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/39276005890)：216 bills +795 backend +14 MockBank passed | 尚未开 PR/合并，Issue #136 仍开放；等名额释放 |
| 06 / 公共业务评测 | [分支 4ff832d](https://github.com/DrErwin/hackerthon-bank-agent/tree/test/bills/public-business-evidence-06)，[真实 17/17 L01 场景](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/39277287794) 成功，固定源码、原始 gzip、来源验证与 SHA256 已入库 | **phase1 partial**，其他功能/错误数量门槛尚未完成，不算全票验收；依赖 #93 合并后提审 |
| 07 / HTTP 导出证据 | [独立分支 cf5e23c](https://github.com/DrErwin/hackerthon-bank-agent/tree/test/bills/report-http-evidence-07) 已更新到含 #151 主线、重钉 backend tree 和 7 条 FastAPI/TestClient 场景 | 新 [Actions 39278072579](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/39278072579) 尚未得到最终结果；旧 7 场景/87 请求只记历史，直播模型/React/安全验收未做 |

注意：上表不同分支、不同层次的测试数量**不相加**。当前每人最多两张未合并 PR 已由 #93、#171 占用，不未经审核擅自合入或越权创建第三张。最新事实以具体 PR/Issue/GitHub Actions 为准；以下历史段落按发生时事实保留。


## 2026-10-19 22:35 · 明日验收前最新个人实证

- **#93 最新验收证据已补齐**：[源提交 `999c1c0`](https://github.com/DrErwin/hackerthon-bank-agent/commit/999c1c062cc946f89bae6607eafe6234f4f76a40) → [原始报告归档 `6540f89`](https://github.com/DrErwin/hackerthon-bank-agent/commit/6540f8997c5a6ed9c85779c18e5348819c148610)。[GitHub Actions 39266604025](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/39266604025) 全检出真实运行 `147 passed/0 failed`，130算术+17工具、14份指定源码 git blob 对齐；新gzip已归档（gzip SHA256 `b00c8b3a961674e54c6b1d658bd54f18bc5579019522e3db66e295db9b766f47`，解压 JSON SHA256 `f18b553f3a7ebdf5b22c3f4946038e9a1603f58ffbfe82a1238ac3e57c572b6d`）。[PR head CI 39267252080](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/39267252080) `727 backend +14 Mock Bank passed`。待 Erwin 正式审核合并，不冒充主线完成。
- **#151 L03 两项审核必修已修**：口语对比、未来月份/9999年输入现在在读银行前追问，新增7个回归；基于主线再次同步后 head `8ffd5ecbe3cc7225fe978c4dbdd56ed4edb28903`，CI [39266305594](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/39266305594) `782 backend +14 Mock Bank passed`，仍待 Erwin 审核、平台安全真实装配。
- **票04 L02**：新主线 F10 `ApiService.input_response(self,task,request)` 改动导致原三项集成用例报错（历史失败 CI [39268776165](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/39268776165)），已只在自己的 `bills/test_anomaly_integration.py` 修正 task-shaped 适配。远端 head `530b887550080d31c766f21a9c7aa601b1db21ef`；新独立 CI [39269422584](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/39269422584) `253 bills +821 full backend +14 MockBank passed`。分支已提交、尚未提 PR/合并。
- **票09（Issue #136）模块防重**：head `fcf3ffca1817105cd1cde6914052a05c9a5b7cc0`，独立 CI [39268776165](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/39268776165) M2 job 118115250041 `161 bills +729 backend +14 MockBank passed`，代码已推分支，仍未提 PR，Issue 保持 open。
- **票10（Issue #145）只读审计**：head `8967b8d7aa5ae3742602f24703ab7145a8e338b8`，同批 CI audit job 118115250557 `161 bills +729 backend +14 MockBank passed`，代码已推分支，仍需 PR 与 Ringo 专业审查；历史审计数据清理另交 Erwin 决策。
- **评测票06/07**：此前公开 L01 有17场景通过，L03/导出 HTTP 有7场景87请求通过；完整每功能≥10、每类异常≥3、真实模型/React/安全与 BF01-BF07 联合验收未满，继续 in_progress，不虚报 accepted。
- **仓库规则和依赖**：本人已开放 PR #93/#151 占用每人最多两张未合 PR 名额。以上 L02/#136/#145 将在 Erwin 审查合并释放名额后按独立 PR 正式提审；不可由 Ethan 代签或自行将代码合到团队主线。平台/安全/前端各自 Owner 接线与审查事项单独登记。


## 2026-10-19 紧急通知后最新远端状态

- PM 在 [PR #93 的 10-19 紧急评论](https://github.com/DrErwin/hackerthon-bank-agent/pull/93#issuecomment-6260156356) 要求 10-20 收口前评测 PR 入主线。本轮核对最新 main `ecf90d0dd8c3b2acdbb0c52c30bdee90581007bc`；七个新增主线提交与本人 PR #93 的 16 个 `evals/bills/` 文件、#151 的 7 个 `backend/app/modules/bills/` 文件均无修改路径冲突。
- **PR #93**：最新 HEAD `6dc39a13b5beb9905e04e4f889e75f623ad44e6d`，父提交为上述 main；新 [Repository checks #39249352055](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/39249352055) success，job 118049030285 的实际日志 **708 backend passed / 14 Mock Bank passed**。147 项专项正式 gzip 对应历史受测 SHA `84b6594e0f989844f62e4c4eaad470e6f1124124`；本轮读取两份完整 Git tree 对照 `run_evidence.py` SOURCE_PATHS：**14/14 Git Blob SHA 完全相同**。这是源码等价补证，**不是对新 HEAD 重跑 147**。新 HEAD 完整检出专项实跑仍须在可执行仓库环境补跑，或 PM 书面认可此补证。已在 [PR #93 评论](https://github.com/DrErwin/hackerthon-bank-agent/pull/93#issuecomment-6266958251) 说明，不能自行合并。
- **PR #151**：最新 HEAD `1223bad158a87f401a999e80c5d26f1e251dd625`，父提交为上述 main；新 [Repository checks #39249437574](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/39249437574) success，job 118049311666 的日志：**756 backend passed / 14 Mock Bank passed**。L03 待 Erwin 审查；生产白名单/注册、真实模型/React 的专业验收单列。
- **#136/09、#145/10**：代码与历史变异测试已在远端 `test/bills/l01-module-dedup-136-09`、`fix/bills/read-audit-evidence-145`；分别已向 [#136](https://github.com/DrErwin/hackerthon-bank-agent/issues/136#issuecomment-6266913325) 和 [#145](https://github.com/DrErwin/hackerthon-bank-agent/issues/145#issuecomment-6266914743) 回填。当前没有单独新 PR 或主线合并。L02、票 06/07 也仍在独立分支，完整 v0.4 任务下限未完成。
- 本人现有两张未合并 PR 为 #93 / #151（Ready，最新 CI 绿），遵守最多两张未合 PR；待审核释放名额才继续单目录提交与合并，其他代码分支不因本文自动获得生产批准。


以下 2026-10-11 记录按当时事实保留；最新推进见文末“2026-10-19 实证续记”。

交付包：[v04-bills/packages/01-bills-backend：账单业务能力与评测](../v04-bills/packages/01-bills-backend.md)
领取人/接受日期：周恩宇（Ethan / @zhouey314-cloud），2026-10-11。
实际开始日期/状态：2026-10-11，in_progress。
规格/七张单目录票：[实施规格](spec.md)。

## 本轮已核对与已执行

- 主线基线65d1a706941f336e1820d64a4f9b662acdc4584e：v0.3已收口、v0.4启动；cross移至v0.5。
- 私有账单计算代码和65项模块单测已完成本地验证，未注册不可调用公开能力。
- 75条新增/细化设计记录与旧21条按ID去重共92条；不是92条业务通过。26个黄金算术样本与模块65项合跑91项通过。
- 发现[Issue #91](https://github.com/DrErwin/hackerthon-bank-agent/issues/91)并指派Erwin：冻结契约B08/公共账单模型尚无实现接缝。

## 实际提交及验证（2026-10-11）

- [PR #92：账单私有统计内核](https://github.com/DrErwin/hackerthon-bank-agent/pull/92)：仅backend/app/modules/bills/，head bdb3f093；已请求DrErwin审查，未合并。执行者自查修复manifest.owner空格不符合公共ID约束的问题，不改变公共模型。
- [PR #93：覆盖/数据/算术层证据](https://github.com/DrErwin/hackerthon-bank-agent/pull/93)：仅evals/bills/，head56975124，Draft依赖#92。前序合入后须更新base并重跑，不叠第三层PR。
- 本地复验：`PYTHONPATH=backend python -m pytest -q backend/app/modules/bills/test_statistics.py evals/bills/test_statistics_eval.py`，91 passed（65模块 +26算术黄金样本）。正式业务92条设计仍未实跑。
- [PR #92 CI](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/38143926981/job/114483229545)失败于主线已有安全文档第58行失效相对链接；不是后端测试失败，因为语法/依赖安装/整仓后端测试尚未执行。#93运行38144027800同样失败于链接检查阶段。
- 已登记[Issue #94：公共文档链接阻塞CI](https://github.com/DrErwin/hackerthon-bank-agent/issues/94)给Erwin协调，未越界修改evals/security。修复后还须基于最新主线复验，不能记CI通过。
- 本人没有实施独立双轴代理审查或Ringo专业审查，没有代签批准，没有合并代码PR。

## 后续范围

PR未合入不记为主线完成；完整业务实现、全部故障样本、真实银行接缝/权限/恢复/模型/HTTP/前端与专业审查仍未完成。公开能力可用后才通知frontend-complete/01接入。

Erwin提供Issue #91的公共类型与B08实现及合入证据后，继续[03公开统计](issues/03-public-summary.md)，随后L02/L03按依赖推进；先就绪的核心路径先联调。#94只是CI阻塞，与#91业务依赖分开。

## 同步说明

本次登记包、本人规格/票据及本台账。共享的docs/01-项目跟踪.md为长历史文档，本轮未覆盖修改，主表领取栏仍需按本包的真实领取记录回填；不声称已更新飞书。相关领取/依赖已通过包、本台账和Issue #91可供Erwin核对。

## 2026-10-19 实证续记

本轮首批受测基线为 `9741053c304a194a4c3d5ab3048f4dbb8be3b0f9`。源码按原始 Git 对象完整恢复并校验；各票在独立工作树实施。10-19 后续 Erwin 已合入 PR #153，main 更新为 `cd7c91ad80652852bb10fef139c2442d756ef359`，本过程文档分支已随之更新。下表分别登记原受测版本与后续状态，尚未合入的 Ethan 工作均不标记 `closed`。

| 本人实施票 | 本轮开发与证据 | 当前状态 |
|---|---|---|
| [02：覆盖、数据与算术](issues/02-coverage-and-fixtures.md) / [PR #93](https://github.com/DrErwin/hackerthon-bank-agent/pull/93) | 新主线固定源码 `84b6594e0f989844f62e4c4eaad470e6f1124124`，完整检出复跑 147 passed、独立专项 50 passed；最终远端 [d367456961679d5431d4f1f534f723c9b6b079d9](https://github.com/DrErwin/hackerthon-bank-agent/commit/d367456961679d5431d4f1f534f723c9b6b079d9)；[CI 39223750787](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/39223750787) success：后端 699、Mock Bank 14 | `in_progress`；证据与新 CI 已补齐，待 Erwin 审查/合入 |
| [04：L02 异常核对](issues/04-anomalies.md) | 最终远端 [ad627f00e4d3ff94d54c612eac4d4499094c0769](https://github.com/DrErwin/hackerthon-bank-agent/commit/ad627f00e4d3ff94d54c612eac4d4499094c0769)，与受测 `2843f6b` 等树；本分支后端 793 passed、bills 253（其中 L02 94），独立修复复核 15 passed | `in_progress`；开发和独立复核完成，分支已推送；待队列、平台/安全正式准入及合入 |
| [05：L03 报告](issues/05-report-export.md) / [PR #151](https://github.com/DrErwin/hackerthon-bank-agent/pull/151) | 新主线最终远端 [f4e672e0d177f87b46239aea1e2ca5668f2e347f](https://github.com/DrErwin/hackerthon-bank-agent/commit/f4e672e0d177f87b46239aea1e2ca5668f2e347f)；[CI 39223073629](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/39223073629) success：后端 747 passed、Mock Bank 14 passed | `in_progress`；待 Erwin 审查/合入；平台和导出纵向验收继续分开 |
| [09：模块防重覆盖](issues/09-module-dedup-test-coverage.md) / [Issue #136](https://github.com/DrErwin/hackerthon-bank-agent/issues/136) | 新主线受测 `74350ce9766e1df0e566de4ac804f2fd7f9081be` 后端 701 passed；等树远端 [38aa8de1063b90462582346d18076761ace59792](https://github.com/DrErwin/hackerthon-bank-agent/commit/38aa8de1063b90462582346d18076761ace59792) 已推送；仍为 1 个 M2 killed、0 survived，2 个测试变红 | `in_progress`；远端分支已更新，遵守同时最多两个未合 PR 的限制，尚未新开第三个 PR |
| [10：只读审计证据](issues/10-read-audit-evidence.md) / [Issue #145](https://github.com/DrErwin/hackerthon-bank-agent/issues/145) | 新主线受测 `1d572f4cf2d9fb02dbb26cfee4b35026dc0d98ac` 本分支后端 701 passed；等树远端 [e6caabe43b981257e58bb5b2905ecff4602daf70](https://github.com/DrErwin/hackerthon-bank-agent/commit/e6caabe43b981257e58bb5b2905ecff4602daf70) 已推送；3 个独立变异均 killed | `in_progress`；新主线本分支回归已通过，待 PR 排队及审查；旧 699/1 保留为历史 |
| [06：完整业务评测](issues/06-full-business-eval.md) | 新版受测源码 [49ab58e21634371313cedc8488da77f25f09e95d](https://github.com/DrErwin/hackerthon-bank-agent/commit/49ab58e21634371313cedc8488da77f25f09e95d)，正式 runner **17 passed**、目录预检 67 passed；最终归档 [0c06511e9470102216e78df5b83f3dc79c2a5c82](https://github.com/DrErwin/hackerthon-bank-agent/commit/0c06511e9470102216e78df5b83f3dc79c2a5c82)；115 源码/44 模块/33 响应/17 银行不变证明 | `in_progress`；17 含旧 14，三项就绪缺口已补；整体数量门槛和剩余分支仍需覆盖，受测版本路径依赖分列 |
| [07：HTTP 与联调证据](issues/07-integration-evidence.md) | 正式受测源码 [5f22c63605ecb83f624f5690f0a76eddff70d185](https://github.com/DrErwin/hackerthon-bank-agent/commit/5f22c63605ecb83f624f5690f0a76eddff70d185)，**7 passed / 87 个实际 HTTP 请求**；最终归档 [a3ae818ceeed3816d0186a221e71df98abd91a4e](https://github.com/DrErwin/hackerthon-bank-agent/commit/a3ae818ceeed3816d0186a221e71df98abd91a4e)；125 源码/60 模块/7 份资金不变证明 | `in_progress`；进程内 HTTP 阶段通过；生产 L02/L03 准入、合法模型配置、页面与专业安全仍分别验收，其余 HTTP 分支属待补覆盖 |

### 已合入的历史切片（本轮校正状态）

- [01 / PR #92](issues/01-statistics-core.md)：已于 **2026-10-13T14:15:48Z** 合入 [8c00f880a8911b4ff8c763e7e1e2e43a1d1f5192](https://github.com/DrErwin/hackerthon-bank-agent/commit/8c00f880a8911b4ff8c763e7e1e2e43a1d1f5192)，本票私有统计内核切片为 resolved；不再沿用 10-11 的待审状态。
- [03 / PR #131](issues/03-public-summary.md)：批准的 L01 模块切片已于 **2026-10-15T17:53:58Z** 合入 [85a119deb3fca629ba7661d01e775babef722623](https://github.com/DrErwin/hackerthon-bank-agent/commit/85a119deb3fca629ba7661d01e775babef722623)。03 仍按其剩余范围保持 in_progress，不把切片合入等同于高级查询、真实模型/页面和专业验收全部完成。
- [08 / PR #140](issues/08-l01-rework-consistency.md) 本来已 resolved；保留原票的 PM 授权代行修复归属与审查记录，不计为本轮新增工作。本轮新增返修是 /09 与 /10，各自独立记录。

### PR #93 证据层次

北京时间 15:56 的前序受测源码为 `17031a174aed5b586032ed4c455b0c594182ab9e`，后继 `eef9b8e998f0adab716e30d7276f264d9181119f` 只归档证据并更新说明。该轮 gzip 为 `evals/bills/evidence/2026-10-19/20261019T075607860590Z-python3.12.14-private-arithmetic-17031a174aed.json.gz`，解压 JSON SHA256 为 `dfd6416bbafcee6f8fd17070ccdc6b42b2d79b5d64b2c837fd14e4b035e6bf33`；原 [CI 39219881038](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/39219881038) success：后端 698、Mock Bank 14。此证据保留为前序基线历史。

16:29 在新主线 cd7c91ad 上固定源码 `84b6594e0f989844f62e4c4eaad470e6f1124124` 再跑，仍为 **147 passed**，独立专项 **50 passed in 0.19s**。新 gzip 为 `evals/bills/evidence/2026-10-19/20261019T082904821548Z-python3.12.14-private-arithmetic-84b6594e0f98.json.gz`，解压 SHA256 为 `e313bdc1de75a5b70b4c10af0bd21138b8131a65aba5c73ac3668f7491e07371`。独立 Spec 复核确认报告与提交原字节一致、14/14 源码指纹匹配、147 条唯一样本及时间有效，旧 4 份证据字节未变。两轮均为 `git_object_verified_source_files`；新一轮真实复跑不累计为新增覆盖。

最新远端 d367456961679d5431d4f1f534f723c9b6b079d9 与本地归档 cac529389e25f5eacfed3bc3f32dbe1786cfb67c 的 Git 树均为 `e2ef7b203df170f4dde5704cbd1e001817f9dc3c`，已核对相等；新 CI 39223750787 / job 117964933338 已 success，后端 **699 passed**、Mock Bank **14 passed**。CI 仍与本目录算术专项分别认定。

统计口径为 **96 条业务设计 / 33 个黄金样本 / 130 项算术 / 17 项工具 / 147 项合跑**。独立 `evals/bills` 的 50 项与合跑中的黄金、工具测试重叠，不能相加成 197 项；各轮 CI 的后端 / Mock Bank 数量也不是新增业务覆盖。运行器 `tier_counts` 的分类缺陷按 PM 既有非阻塞结论保留，原始报告未手工改写。

### 票 06 首批公共业务证据

基于已发布源码 `7439ced9136984f9f4be27342b6adb0c7726cc14` 实跑，开始 `2026-10-19T08:41:46.267213+00:00`，结束 `2026-10-19T08:41:50.875779+00:00`。14 collected / **14 passed / 0 failed / 0 skipped / 0 errors / 0 collection errors**，pytest 输出 `14 passed in 3.75s`；运行器逐项核对 115 份源码、44 个实际 app 模块、27 条公共响应，以及 14 个场景的银行表摘要/余额不变和零资金提交。

原始报告为 `evals/bills/evidence/2026-10-19/20261019T084150880617Z-python3.12.14-public-l01-phase1-7439ced91369.json.gz`，解压 SHA256 **`af6f959b06cbcc1a7518c08540a2e3eb25e3f2e6edbc90d92421e26b9ff31cd1`**。最终归档远端 `6b77cc28c7af97a9a1028e7d68726f01b92daee6`，树 `84f9daef8f63645feb5799b4bcfa469dfca21abf`；源码与归档前后分开，旧 5 份证据原字节未变。

14 项通过指断言符合预期，实际最终业务状态为 **10 succeeded、2 正确拒绝 failed、1 waiting_input、1 cancelled**。7 条 Blocked 只描述本次 L01 受测版本的未运行路径，L01 自身缺例另列 remaining_coverage；不是全项目当前状态，也不把这些状态转换成 7 项通过。此报告的 Planner/权限/LOW 风险策略仍是明确替身，没有声明真实模型、HTTP、页面或专业安全验收。

### 票 06 新版 17 场景证据

独立范围复核发现三个已可验证的 L01 缺口，已补齐退款原单补查失败后恢复、非空银行范围的类别无匹配、排除普通类别时的零读澄清。受审源码 25d13701787db8fafb91c7cf8f6976edbe909981 与正式受测 [49ab58e21634371313cedc8488da77f25f09e95d](https://github.com/DrErwin/hackerthon-bank-agent/commit/49ab58e21634371313cedc8488da77f25f09e95d) 等树 `47feaf95b286c8c089c30f583a08d8f80bfce939`，两轴独立增量复核通过。实际正式运行 `2026-10-19T08:59:21.194006+00:00`—`08:59:26.331989+00:00`：**17 passed in 4.36s**，failed/skipped/error/collection_errors 均为 0；目录预检 **67 passed in 3.91s**。

新原始报告 `evals/bills/evidence/2026-10-19/20261019T085926337455Z-python3.12.14-public-l01-phase1-49ab58e21634.json.gz`，解压 SHA256 **`28a3f25af3c9c50f1cc640acfe51da7ca7f8290905a19732a7723742c62fbe57`**；最终归档 [0c06511e9470102216e78df5b83f3dc79c2a5c82](https://github.com/DrErwin/hackerthon-bank-agent/commit/0c06511e9470102216e78df5b83f3dc79c2a5c82)，树 `50f20da211ccd710a4ce6aa4e90a522d3cd24797`。115 份源码、44 个导入模块、33 条公共响应和 17 份银行不变证明均核对通过；旧 6 份原始证据字节未变。

17 项最终业务状态为 **13 succeeded、2 正确拒绝 failed、1 waiting_input、1 cancelled**。这是完整复跑的新版 17，包含前述 14，不能累计为 31；67 为既有 50 项专项加当前 17，也不与算术 147 相加。完整票的每子功能 ≥10、每类异常 ≥3 和尚列出的范围/比较/边界/错误分支未全部满足，继续 `partial`；HTTP 的另层证据见票 07。

### 票 07 报告与两层导出 HTTP 证据

在已发布验证组合 [99e96737792f375387ca3eb532ff2be0478af33e](https://github.com/DrErwin/hackerthon-bank-agent/commit/99e96737792f375387ca3eb532ff2be0478af33e) 上完成独立 `evals/bills/` 增量，实际受测源码 [5f22c63605ecb83f624f5690f0a76eddff70d185](https://github.com/DrErwin/hackerthon-bank-agent/commit/5f22c63605ecb83f624f5690f0a76eddff70d185)，树 `fd1481e19ac27b9703c74073fbd9ee67be879653`。该组合与本地 ee470d5 等树，不代表已合入 main 或生产获准。先前源码 7b06c215 的正式 runner 在测试前拒绝不存在的 `security/executor.py`，没有生成 raw；仅修正两项真实路径后，独立正向来源核验通过，再执行本轮正式运行。

正式运行 `2026-10-19T09:01:53.927591+00:00`—`09:02:00.176938+00:00`：**7 passed in 5.28s**，failed/skipped/error/collection_errors 均为 0，共 **87 个 HTTP 请求**。原始报告 `evals/bills/evidence/2026-10-19/20261019T090200185196Z-python3.12.14-http-l03-exports-5f22c63605ec.json.gz`，解压 SHA256 **`25c4a1a45664e70f05e36ce44872c5f667164b6fc5f3a0f208beadc8e987e823`**。根执行者独立核验 125 份 Git 源码、60 个实际导入模块、7 个唯一样本及 87 个请求；所有非银行验证表摘要不变，资金提交为 0。

最终归档 [a3ae818ceeed3816d0186a221e71df98abd91a4e](https://github.com/DrErwin/hackerthon-bank-agent/commit/a3ae818ceeed3816d0186a221e71df98abd91a4e) 已推到 `test/bills/report-http-evidence-07`，树 `7d3ff1269b78022ec651d091a82ddfa9a6394a32`，父提交为实际受测 5f22c636；只归档原始报告和说明，未改受测代码，也未另开 PR。

七场景分别证明真实 L03 自动报告落库及聊天一致、普通 card 直接导出、details 验证前拒绝/验证后逐字段 CSV、连续错码拒绝、银行截止时点过期、跨用户资源拒绝、跨会话敏感授权失效。F17 的到期 POST 为 **409 TASK_TERMINATED**，导出状态为 **VERIFICATION_EXPIRED**，按实际层次分开。银行验证会合法产生验证记录，不将其说成银行全表不变。

本阶段使用真实 FastAPI TestClient/ApiService、L03/Harness/SQLite、Gate/执行器及银行验证，Planner 与窄准入/LOW 风险输入为明确替身。F21、自动报告持久化和 F22—F24 已实跑贯通；默认 `local_demo` 仍只登记 L01、生产策略尚需 L02/L03 准入，当前没有 `BANK_LOCAL_CONFIG` 合法模型配置，React 页面与专业安全仍需对应验收。其余 HTTP 分支、部署网络/SSE 及自然语言路由测试缺口分别列在 [07](issues/07-integration-evidence.md)，不泛称 HTTP 接口不存在。七场景的 `phase_result=Passed` 与整票 `overall_status=partial` 同时保留。

### #145 全量失败与共享底座边界

本节先保留 PR #153 合入前的运行历史。该补丁已由 Erwin 正式合入 [main cd7c91ad80652852bb10fef139c2442d756ef359](https://github.com/DrErwin/hackerthon-bank-agent/commit/cd7c91ad80652852bb10fef139c2442d756ef359)；#145 已完成新主线本分支回归，**701 passed in 126.08s**。旧共享引用缺陷及 699/1 结果不再作为现行外部阻断。

全后端的唯一失败是订阅测试 `test_changed_bank_facts_cannot_reuse_the_answered_confirmation`：首次任务因 `SecurityError` 成为 `FAILED`。原结果保留 **699 passed / 1 failed**，不把 bills + API 的 237 passed 写成整仓全绿。

Erwin 的 [PR #153](https://github.com/DrErwin/hackerthon-bank-agent/pull/153) 已说明共享审计数字掩码可能损坏不透明的 `*_ref` / `*_refs`。本票不越界修改共享审计实现。`parameters_sha256` 仍可能被现有数字掩码改变，这是另一项共享底座限制；不能把引用保护补丁等同于摘要掩码也已解决。

根执行者在本地 /09 + L03 + #145 合成验证树中，使用 Erwin PR #153 新增的精确 `test_journal.py` 回归对照：原 main 的 journal **1 failed**，错误为 `snapshot is not referenced by event`；只替换为该 PR 的精确 journal 文件后 **1 passed**。同一合成树 + PR #153 再跑原失败订阅用例及全 bills，**212 passed in 4.68s**。这支持“主线存在同类引用缺陷，需共享补丁”的依赖解释；原失败临时数据库已不可重读，未声称已完整重建那次失败的因果链，也不把合成结果算作 #145 本分支全绿。

### 尚待完成的验收

当前本人未合 PR 为 #93、#151，其他已推分支按最多两个未合 PR 的限制等待队列及审查；历史运行不移记为新版本证据。PR #153 合入前，根执行者曾在本地合成验证树组合 /09、L03 和 #145，并仅在该树临时叠加 Erwin 的精确补丁做依赖核验；合入后，新分支直接继承新 main 的上游文件，不把这两份上游变更算作 Ethan 的越界增量。

新主线 cd7c91ad + 本轮 /09、L03、#145、L02 四票的本地合成模块提交 `ee470d5f546b799a393ba3431e6d4db44cbf333c`，树 `7104421676366632a1bc6861c9fd0e283f6fb2a0`，已经实际完成 **后端 845 passed in 127.03s，Mock Bank 14 passed in 0.47s**。这是本地组合回归，不替代各分支审查/CI 或合入事实，也不作为新增业务设计数量。212 项旧组合结果保留为前序验证历史。

组合后端用例数量核对为 **699 项核心基线 + L03 新增 48 + L02 新增 94 + 审计新增 2 + 模块防重新增 2 = 845**。这只是同一组合版本的计数一致性检查，不将不同分支的 747、793、701、701 等回归结果相加为新覆盖；公共业务与 HTTP 场景另按票 06 / 07 分层记录。

L02 按 [04](issues/04-anomalies.md) 单独实施和记录；报告持久化与 F21—F24 已有票 07 的实际 HTTP 层证据，生产规划/权限装配、页面、合法真实模型运行及专业安全结论仍以对应路径验收为准。本次只更新本人过程文档，不代表共享项目进度或对外通知已同步。
