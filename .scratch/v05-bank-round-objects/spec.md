# 银行对象轮次归属与跨轮次拒绝工作规格

Status: blocked — 2026-10-26 只读核查与责任判断完成；存储、服务两票已拆，评测收口票在银行评测组；实施等生日 storage 05 目录窗口与提供方合入。

Owner: Erwin（v0.5 本阶段统一负责）

Accepted by: Erwin（2026-10-26 01:17 会话指令原文：“阅读 handoff…，开始工作。编码避开生日线共用目录”；本会话按交接范围只做只读核查与拆票，实施/验收另记，不由本记录推算）

Accepted at: 2026-10-26

Package: [v05-cross-linkage/packages/01-platform-bank：公共接缝与模拟银行](../v05-cross-linkage/packages/01-platform-bank.md)

Work spec 依据：[银行接口字段](../../docs/contracts/银行接口字段-2026-09-24.md)、[安全与审计字段](../../docs/contracts/安全与审计字段-2026-09-24.md)、[公共契约 §6.9 / §7](../../docs/contracts/公共契约-2026-09-23.md)，以及[包 06 银行专项验收](../v05-cross-linkage/packages/06-bank-eval.md)第 4 条。

## 背景与范围

[PR #290](https://github.com/DrErwin/hackerthon-bank-agent/pull/290) 的四项 strict xfail 记录：同用户、同银行库，把可信上下文从 D1 换到 D2、用新操作编号后，裸银行仍可读取旧冻结/旧订单并核销/释放。原探针只走显式测试授权，没有真实安全执行器，不能据此断言 HTTP/页面可越权。

2026-10-26 只读核查（见[核查与责任判断](verification.md)）结论：

- 产品路径的上游门已覆盖：旧会话/任务按轮次拒绝（401/404）、真实安全 claim 与旧释放授权拒绝、平台订单来源门（#296）在确认前/执行前拒绝跨任务与旧轮次订单；B13/B22 不是模型工具、无 HTTP 路由。
- 原约定仍要求银行在**对象归属层**独立拒绝：银行是冻结/订单事实的唯一所有者，B13/B22 的归属错误码、安全附件的“可信身份与资源归属 / 同轮次 / 银行仍校验原冻结释放权限”都落在银行边界；银行已按 `(user, round)` 绑定操作编号，但对象表没有轮次归属，属同一规则内的缺口。
- 因此不新增业务政策、不改公共契约字段，只补对象轮次归属并在读写时校验；平台/安全当前无需新规则。

## 涉及目录与票

新建本工作组而非在 `v05-cross-platform` 继续追加的理由：包 01 的既有 01—15 号票分别承载平台接缝、生日银行能力与在途平台修复，账目按票号追踪；本次是不预设四个目录的跨层小修复（storage→services），与任何既有票的实施顺序和 PR 边界都不同。按 issue-tracker 的“同一组长工作集中编号”，单独建组能保持单目录一票/一 PR，评测收口仍留在银行评测组（包 06）。

每票只改一个归属目录：

- [v05-bank-round-objects/01：存储层对象轮次归属](issues/01-object-round-storage.md) — `backend/app/storage/`。
- [v05-bank-round-objects/02：银行服务与网关按轮次校验对象](issues/02-object-round-services.md) — `backend/app/services/`，依赖 01。
- [v05-cross-bank-eval/02：跨轮次对象边界回归收口](../v05-cross-bank-eval/issues/02-round-object-regression.md) — `evals/mockbank/`，依赖 02。

## 约束

- **不做共享库迁移**：已有 v4 演示银行库若已有冻结/订单行，明确拒绝加载并保留原库、要求显式启用新库（沿用 `services/mock_bank/README.md` 旧操作库先例）；空对象表的 v4 库原地加列；不静默改写或清除历史事实。
- 开发与验证只用全新绝对隔离数据目录；不读写共享 `.mnemon/` 演示库或原 E2E 库。
- 同轮正常路径保持：B10→B21→B11→B12、原操作回查、响应未知沿原编号恢复、合法订单只付一次、缺失对象仍为 `RECORD_NOT_FOUND`。
- 跨轮对象：读取与写入返回 `ACCESS_DENIED`（不存在仍 `RECORD_NOT_FOUND`），不得移动资金或留下成功回执。
- 中间态：存储票先提供可选归属参数；服务票再把所有写入/读取接入并打开校验。两票之间不能视为可运行演示状态。
- 修复导致原四项 strict xfail XPASS 是预期信号，由评测票人工转换；不删测试、不降期望、不改历史证据。

## 验证与完成

- 每票只做本目录局部验证（隔离临时库）；代码交付另做两位独立子代理规范/规格审查、必修项修复、独立 PR 回交，不自行合并。
- 评测收口后分两个口径记录：①`evals/mockbank/test_birthday_bank_eval.py` 单文件 41 项（原 37 通过 + 4 项转正）全部通过、0 xfailed；②`birthday-evidence.md` 记录的合跑命令按实施后实际节点全绿、0 failed/0 xfailed（2026-10-25 为 153 节点、2026-10-26 收集 175 节点，按实际记录不写死数量）；保留合法订单/同轮对照与历史失败 XML。
- 不自动运行：真实页面/模型/银行全链 E2E、B26 正式重置、整体银行专项接受、安全专项、Ringo 真人签核、PM 最终接受。

## 协调与停止线

生日系列共用 `backend/app/storage/`（下一步 [v05-birthday-platform-dependencies/05：生日编辑候选检查点的一次封存](../v05-birthday-platform-dependencies/issues/05-immutable-edit-checkpoint.md)）与可能的 `backend/app/services/`。2026-10-26 01:20 生日线正在 `agent_platform`（数量票，本地提交 `189c651`）实施；本系列按“生日 storage 05 完成 → 本组 01 → 本组 02 → 评测 02”顺序申请目录窗口，未获窗口前不写共用目录。共享项目跟踪与版本 completion 由本轮生日协调者统一维护，本组只更新自己的票据并回交。
