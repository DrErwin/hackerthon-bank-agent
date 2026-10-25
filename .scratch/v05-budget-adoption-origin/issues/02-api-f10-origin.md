# 02：原 F10 输入身份接入平台来源

Ticket ID: v05-budget-adoption-origin/02

Package: [v05-cross-linkage/packages/01-platform-bank：公共接缝与模拟银行](../../v05-cross-linkage/packages/01-platform-bank.md)

Spec: [预算采用来源最小设计](../spec.md)

Type: 开发

Owner: Erwin

Directory: `backend/app/api/`

Status: delivered_api_seam — API接缝、定向93项与双轴审查已完成，待本票PR和中控排队；真实cross06/#293采用及完整E2E仍待下游，不代表合入或真人安全批准。

Blocked by: None（平台01已实际合入，中控开始信号已收到）；真实cross06/AdoptedBudget及完整生日验收仍属后续依赖。

Execution thread: `01a171b0-4bf1-7571-bf2c-7c85c404329d`（原来源设计对话）。Accepted by: Erwin委派本对话；Accepted at: 2026-10-25。独立managed worktree v05-budget-f10-api；分支 codex/v05-budget-f10-api；基线6ce7fb03。只改API与本票材料，不包含恢复503诊断、生日编辑G1/04、共享跟踪或completion。

Core scenarios: O01—O08，定义见规格。

## What to build

既有 F10 请求体不变，仅专用预算候选选项路径保留原 request/interaction/option 并调用平台专用方法。聊天 provide_input 留在普通路径，不可借用来源。仅有原持久来源的精确中断请求可走受控恢复，不给所有 F10 放开重做。

## Acceptance criteria

- [x] Cookie/同源、任务归属、原交互和选项检查保留；不接收 source=human、actor、plan_version 或候选摘要作为证明。
- [x] 专用 F10 与模型续答的模块 response 即使相同，当前后台来源接口仍能区分；模型不能调用专用入口。
- [x] 同号同参返回原 receipt，同号异参拒绝；同交互不同号不得重复采用。
- [x] receipt 键不含 session 的既有事实不能扩大来源使用范围；原来源的主体/会话/轮次/任务另核验。
- [x] 处理 accepted 前/后、completed 后/receipt 前断点；只恢复原来源和原结果，不重新生成来源、不用当前新任务结果替代原结果。
- [x] 原 receipt/来源/attempt 历史核实在普通 current_input_task 之前严格分流；缺历史证据不绕过当前交互检查，已采用的补结果不重新授权。
- [x] 普通 F10 金额/日期/配送及非预算输入继续原协议，确认/验证和未知银行动作不受影响。
- [ ] 与 cross06 接通后证明真实采用只发生于专用原 F10，缺来源的模型路径零 AdoptedBudget 写入；完整生日验收仍复用原 E2E 票。

## Verification

通过真实TCP HTTP + 真实Harness/持久来源/检查点验证O01—O08在API接缝的范围；预算业务与planner为明确替身，不以monkeypatch source=true代替。详见[实施/调用/场景矩阵](../api02-implementation.md)、[独立代码审查](../api02-review.md)与[证据摘要/哈希](../api02-evidence/summary.json)。

最终受测HEAD `355ea4ed981764149ed03c1d2bc4007366efc7db`，基线origin/main `2a070b9cf992a109d8b54718a49dc3e3b56bd236`：定向93 passed / 96.15s，失败/错误/跳过均0，其中新增预算API23、平台35、相关API35。日志/JUnit/解释器/命令/head已持久保存；最初8a9b6c9上的93项136.64s保留为独立旧批，不混称本批。

主线同步使用range-diff确认本票两条实现提交等价：753da39→9365d74、8a9b6c9→355ea4e。Standards必修0；Spec初轮发布混批问题已修并复审必修清零，建议0。按中控资源要求仅定向，不跑完整后端；后续需要全量应先报中控排时。

真实cross06/#293 AdoptedBudget写入、真实模型/React页面和完整生日E2E没有在本票验收，以上最后一项仍保留未勾选。未修改共享跟踪/completion，未实施生日编辑G1/04，本票PR未经中控另行批准不得自行合并；不自动沿用之前PR的CI例外。
