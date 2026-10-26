# 银行对象轮次归属与跨轮次拒绝工作规格

Status: in_progress — 2026-10-26 01（storage）已合入 main `819bbfb`；02（services）已合入 main `b63ec1b`；评测收口 02 已完成验证并待 PR 合入。PM 已确认防御纵深决策并授权继续。

Owner: Erwin（v0.5 本阶段统一负责）

Accepted by: Erwin（2026-10-26 01:17 会话指令原文：“阅读 handoff…，开始工作。编码避开生日线共用目录”；本会话按交接范围只做只读核查与拆票，实施/验收另记，不由本记录推算）

Accepted at: 2026-10-26

Package: [v05-cross-linkage/packages/01-platform-bank：公共接缝与模拟银行](../v05-cross-linkage/packages/01-platform-bank.md)

Work spec 依据：[银行接口字段](../../docs/contracts/银行接口字段-2026-09-24.md)、[安全与审计字段](../../docs/contracts/安全与审计字段-2026-09-24.md)、[公共契约 §6.4 / §6.5 / §7 / §9 M14](../../docs/contracts/公共契约-2026-09-23.md)、[MockBank PRD 重置语义](../../docs/prd/MockBank-PRD-2026-09-23.md)，以及[包 06 银行专项验收](../v05-cross-linkage/packages/06-bank-eval.md)第 4 条。

## 背景与范围

[PR #290](https://github.com/DrErwin/hackerthon-bank-agent/pull/290) 的四项 strict xfail 记录：同用户、同银行库，把可信上下文从 D1 换到 D2、用新操作编号后，裸银行仍可读取旧冻结/旧订单并核销/释放。原探针只走显式测试授权，没有真实安全执行器，不能据此断言 HTTP/页面可越权。

2026-10-26 只读核查（见[核查与责任判断](verification.md)）结论：

- 产品路径的上游门已覆盖：旧会话/任务按轮次拒绝（401/404）、真实安全 claim 与旧释放授权拒绝、平台订单来源门（#296）在确认前/执行前拒绝跨任务与旧轮次订单；B13/B22 不是模型工具、无 HTTP 路由。
- **责任分层**：释放收尾链路有明文（公共契约 §9 M14 把“错误轮次拒绝”列给 cross+security+mockbank；安全附件 §3.1“银行仍校验可信主体对原冻结的释放权限”）；B13/B22 读取与 B11 核销只有归属语义 + 包 06 第 4 条，把轮次纳入对象归属是**防御纵深实现决策**，不是契约字面要求。
- **规范的轮次切换是 B26 整体重置**（清除流水/预约/冻结/订单），当前 F30/F31 未实现；四项探针模拟的“同库换 round 不重置”不是规范支持方式，不能据此指控产品可越权。但四项探针已按包 06 第 4 条冻结，改评测去适配平台门等于降低冻结要求；本组建议补对象归属，让银行层能独立收口。
- **该决策已由 Owner 确认并记录**：PM 2026-10-26 16:00 在会话中明确确认「确认按推荐方案继续」（补对象轮次归属、继续 02/评测并开 PR）；不新增业务政策、不改公共契约字段、不复制银行规则到业务模块。

新建本工作组而非在 `v05-cross-platform` 继续追加的理由：包 01 的既有 01—15 号票分别承载平台接缝、生日银行能力与在途平台修复，账目按票号追踪；本次是不预设四个目录的跨层小修复（storage→services），与任何既有票的实施顺序和 PR 边界都不同。按 issue-tracker 的“同一组长工作集中编号”，单独建组能保持单目录一票/一 PR；评测收口仍在银行评测组（包 06）。

## 涉及目录与票

每票只改一个归属目录：

- [v05-bank-round-objects/01：存储层对象轮次归属](issues/01-object-round-storage.md) — `backend/app/storage/`。
- [v05-bank-round-objects/02：银行服务与网关按轮次校验对象](issues/02-object-round-services.md) — `backend/app/services/`，依赖 01。
- [v05-cross-bank-eval/02：跨轮次旧对象边界回归收口](../v05-cross-bank-eval/issues/02-round-object-regression.md) — `evals/mockbank/`，依赖 02。

**跨包要求**：两票挂在包 01（唯一覆盖 storage/services 的包），收口的是包 06 第 4 条；须在包 01 验收/回交中登记，评测票在包 06 收口。

## 约束

- **Owner 决策前置（已满足）**：补对象轮次列属防御纵深实现决策（见背景），PM 2026-10-26 16:00 已确认按推荐方案继续。若后续 Owner 改判“产品层接受、不加对象轮次字段”，则本组两票作废，改为在包 06 记录边界与例外，四项 strict xfail 保留。
- **不做共享库迁移**：已有 v4 演示银行库若已有冻结/订单行，明确拒绝加载并保留原库、要求显式启用新库（沿用 `services/mock_bank/README.md` 旧操作库先例）；空对象表的 v4 库原地加列；不静默改写或清除历史事实。核查时只读抽查本机 `.mnemon` 两个演示库：`v03-local-demo` 为 v3（13 ops / 13 scopes / 0 unscoped）、`v03-local-demo-browser-regression` 为 v2（2 / 2 / 0），均无对象表；无 scope 检查不会拒绝，若加载会按 v2/v3 路径升到 v5 空对象表；未发现 v4 且含对象行的库。
- 开发与验证只用全新绝对隔离数据目录；不读写共享 `.mnemon/` 演示库或原 E2E 库。
- **错误码**：跨轮拒绝统一 `ACCESS_DENIED`（银行接口字段 §8/§2：无权访问目标、不透露存在性）；`RECORD_NOT_FOUND` 只表示授权范围内确不存在；禁止 `OPERATION_CONFLICT` 冒充跨轮拒绝。读取须“先按 user 取行、再比较轮次”，不下推存储过滤。
- **NULL 收口**：存储票的可选轮次参数只服务分阶段兼容，生产写入必须带轮次；02 在 `MockBankService` 初始化时拒绝加载无轮次对象行（镜像 `core.py:103-110`），避免冻结余额被 NULL 行卡死；两票之间不是可运行演示状态。
- **XPASS 时序**：02 合入后四项 strict xfail 变 XPASS，专项在 main 会红到评测票合入；须先备好评测票，按 01→02→评测 02 相邻合入，或由中控记录接受红灯窗口及对 `evals 57+4` 冒烟口径的临时影响。
- **安全审阅**：两票新增 ACCESS_DENIED 判定属资金执行链路；按根 AGENTS.md 由 Erwin 在 v0.5 阶段代行审阅并如实记录（不写 Ringo 签核），或由 Owner 判定不构成新安全规则并在票面留痕。
- 同轮正常路径保持：B10→B21→B11→B12、原操作回查、响应未知沿原编号恢复、合法订单只付一次、缺失对象仍为 `RECORD_NOT_FOUND`。
- 修复导致原四项 strict xfail XPASS 是预期信号，由评测票人工转换；不删测试、不降期望、不改历史证据。

## 验证与完成

- 每票只做本目录局部验证（隔离临时库）；代码交付另做两位独立子代理规范/规格审查、必修项修复、独立 PR 回交，不自行合并。
- 评测收口后分两个口径记录：①`evals/mockbank/test_birthday_bank_eval.py` 单文件 42 项（原 37 通过 + 4 项转正 + 1 混合轮次订单）全部通过、0 xfailed；②`birthday-evidence.md` 记录的合跑命令按实施后实际节点全绿、0 failed/0 xfailed（2026-10-26 实际 217 passed；不写死历史节点数）。四项都断言具体拒绝码（读取/写入 `ACCESS_DENIED`，不接受 `OPERATION_CONFLICT`），保留合法订单/同轮对照与历史失败 XML。
- 不自动运行：真实页面/模型/银行全链 E2E、B26 正式重置、整体银行专项接受、安全专项、Ringo 真人签核、PM 最终接受。

## 协调与停止线

生日系列正在实时使用 `backend/app/storage/`（2026-10-26 01:40 分支 `codex/v05-birthday-immutable-checkpoint` 提交 `3e38506 feat(storage): 候选检查点一次封存与应用库 v7`、`c886660`，改动含 `storage/README.md`、`application.py`、`checkpoints.py`）；本组 01 也改 `storage/README.md`，须等其合入后 rebase 并处理冲突。生日系列 §4 第 4 条写明若验证码原子撤离需要 services 会新增单目录票，因此本组 02 的 services 窗口按“生日需要的目录先完成”排队，不是假设其永不使用 services。评测票在 `evals/mockbank/` 不与人共用，但仍等 02 合入顺序。共享项目跟踪与版本 completion 由本轮生日协调者统一维护，本组只更新自己的票据并回交。
