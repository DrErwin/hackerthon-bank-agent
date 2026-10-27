# 前端三票合入与剩余工作核查（2026-10-27）

Owner: Erwin（v0.5 统一负责）；执行与证据整理：本对话 AI。

授权：用户在已获知 CI 计费阻塞、真实转账暂停及部分验收未完成后，明确要求“先把最新的pr什么的都合并了，然后检查还有什么没完成的”。本次范围为当时全部开放 PR #318、#319、#320；不扩大为风险政策修改、真实业务重跑、共享库迁移或最终验收接受。

## 已合入

| PR / 实施票 | 最终 PR head | squash 提交 | 本次本地验证 |
|---|---|---|---|
| [#318](https://github.com/DrErwin/hackerthon-bank-agent/pull/318) / [frontend-design-system/01](../frontend-design-system/issues/01-foundation.md) | `a69ebc93b965ad6512cd9ed4dda04db14eb9d5ed` | `2a9ebf7ed37c6e210c30edffcdf9ccb4032ac776` | 合入后 12 文件、108 passed；默认构建通过 |
| [#319](https://github.com/DrErwin/hackerthon-bank-agent/pull/319) / [frontend-design-system/02](../frontend-design-system/issues/02-conversation.md) | `4c8cf37cd61af3ba6eb3239c5c538ff085dcaaf7` | `a2386e6b5515af6301e58a7ff7ac9a7a7ff272ca` | 等价同步后 13 文件、113 passed；默认构建通过；合入树相同 |
| [#320](https://github.com/DrErwin/hackerthon-bank-agent/pull/320) / [frontend-design-system/03](../frontend-design-system/issues/03-all-journeys.md) | `db3b58fc2801b34f883b8336575ff0b78183bd44` | `443e9b10fbf99ca0d0ad61c2c7f0e5427adf0b1e` | 合入后 14 文件、122 passed；真实 API 与 contract-demo 两种构建通过 |

- 按 #318 → #319 → #320 顺序 squash。后继分别剔除已 squash 的前序提交，再以 main 为目标；使用带原 head 的 lease 推送，合并使用 expected head。
- #319、#320 的 range-diff 分别 4/4 等价，原/新完整文件树相等。最终 main `443e9b10` 的完整树为 `44da105424fd78b320e7e0fea86ce412081e8ea6`，等于修后受测 `d2309c4a`；frontend 树为 `e549a87ae1f6695ed5e184bc73fe8db73c25be4e`。
- 合并后查询开放 PR 为 0。原 D 盘工作区未切分支或覆盖文件，未跟踪的原型保留；业务库、私密配置和原失败证据未修改。

## Standards

独立初审 1 项必须修复（P2）：恢复资料的默认提示“可以接着办”也会出现在安全暂停任务上。新增实际组件与恢复 hook 的点击回归，在原代码上失败；修为“已找回上次的办理资料，请查看当前进度。”，保留任务暂停状态、空动作列表且不调用服务端恢复。限定复审原问题 resolved，0 剩余必须项。

## Spec

独立初审 0 必须项；限定复核上述恢复提示与回归后，0 必须项。确认、验证、配送清理及原任务恢复边界保持；AI 审查不代替真人体验或安全签核。

## 验证边界

- 本次实际运行：`npm ci --no-audit --no-fund`；各阶段 `npm test -- --reporter=dot`、`npm run build`；最终另以 `VITE_API_MODE=contract-demo` 构建；`python .github/scripts/check_links.py`、启动脚本 Python 语法、差异空白检查。
- 三 PR 最终 head 的 Repository checks 均核对到“job was not started”及账号支付/支出额度注释：[318](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/40305646843)、[319](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/40457127389)、[320](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/40457267163)。远端为计费阻塞，无 CI 通过结论；本次依据用户明确合并指令及本地验证合入。
- 合入后 main `443e9b10` 的 [push 检查](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/40457335336) 也已核对到同一计费未启动注释。后续纯文档回填只做内容、链接及空白核对，不运行或等待 CI；7 份 Markdown 的 183 个本地链接核对通过。
- 本次未运行后端全量、真实模型、HTTP/页面/银行 E2E、200%/读屏或真人验收。历史后端 2121 passed / 13 skipped 是 10-26 记录，不计成本次结果。构建保留大于 500 KB 提示。

## 合并后仍未完成

以下按比赛 Demo 收口优先级排列；实施、验证和本人接受分开记录。

| 优先级 | 事项与实际缺口 | 现有入口 |
|---|---|---|
| P0 | 真实转账后半程：最新真实页面的“转账500元给妈妈”停在风险事实覆盖不足，未到确认/验证/回执。有限危险文本检测已接入，普通低中风险仍依赖流程夹具；真实来源、覆盖和未知处置需按既有票决定及实现，不能放宽未知放行来获得成功 | [#160](https://github.com/DrErwin/hackerthon-bank-agent/issues/160)、[风险裁定材料](../v05-risk-decision/decision.md)、[暂停原始证据](../frontend-design-system/evidence/all-journeys/backend-safety-pause.json) |
| P0 | 三个生活目标完整真实 E2E：减支原 S01 失败保留，修后尚无新完整批次；养老金只验部分准备/停止路径；生日只到方案核对，未采用、冻结、采购、付款和最终收尾。个人预算真实采用也待证明。#301/#302 修复代码已随 #303/#304 合入，不能再称未实施，也不能据此宣布 E2E 通过 | [执行交接](../v05-cross-e2e/manual-execution-handoff.md)、[最新页面报告](../frontend-design-system/e2e-03.md) |
| P0 | 稳定演示环境及重复运行：可重置、可重复的独立验收记录和 B26 正式重置仍缺。银行跨轮次四项 xfail 已转正，不再列为待修；旧库/共享库迁移与回退需按现有方案单独处理，不能删除原库来冒充重置验收 | [v0.5 完成情况](../../docs/versions/v0.5.0/completion.md)、[银行交付边界](../v05-bank-round-objects/verification.md) |
| P0 | 比赛提交包：仓库内未见最终技术文档、答辩 PPT、安全自评与完整源码交付包，v1.0 仍计划中；现有 README 更新不等于全新环境复现通过。报名/平台字段未核验；安全自评必交/可选冲突待官方答疑确认，演示视频为可选 | [v1.0 需求](../../docs/versions/v1.0.0/requirements.md)、[v1.0 完成情况](../../docs/versions/v1.0.0/completion.md) |
| P1 | 生日已知实现缺口：跨会话恢复接线、普通输入发布断点的 API 自动恢复、旧任务编辑不可用；同参新尝试的安全语义接受待本人。核对正文仍出现内部配送引用与付款账户 A1，缺少可读掩码；电话格式需契约明确后统一，不能擅自规定地域手机号格式 | [生日交接](../v05-birthday-platform-dependencies/delivery-handoff.md)、[页面后续项](../frontend-design-system/verification-03.md) |
| P1 | 安全专项与最终接受：96 条新增样例仍 NOT_RUN，既有批次 B/C 等完整专项未补齐；本阶段本人安全审查/接受和 #227 用户最终体验仍待。历史 Ringo 真人签核缺失仍如实保留 | [v0.5 完成情况](../../docs/versions/v0.5.0/completion.md)、[#227](https://github.com/DrErwin/hackerthon-bank-agent/issues/227) |
| P1 | 适老化与恢复验收：已有桌面/390px、大字、部分键盘焦点证据；200% 缩放、完整读屏、真机软键盘，以及新版人为断网/未知银行结果尚未验证 | [前端验证](../frontend-design-system/verification-03.md) |
| P2 | 账号 CI 计费恢复；#216 四项观察能力的 PM 接受及是否另做粘贴框/记忆页；语音范围决定。构建大包优化是后续项，未列为本次合入阻塞 | [项目跟踪](../../docs/01-项目跟踪.md)、[#216](https://github.com/DrErwin/hackerthon-bank-agent/issues/216) |

本次只完成 PR 收口、必要前端修正、本地验证与现状核查。实际业务 E2E 仍遵循既有停止线，未自动启动；v0.5 不标记完成，v1.0 不标记已交付。
