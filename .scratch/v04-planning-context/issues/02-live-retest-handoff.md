# v04-planning-context/02：真实运行复验与移交

Ticket ID: v04-planning-context/02
Package: PM 自拆（不开交付包）；Source issue [Issue #84](https://github.com/DrErwin/hackerthon-bank-agent/issues/84)
Spec: [v04-planning-context 规格链接](../spec.md)
Core scenarios: SEC-C-001 代表变体（v01—v06 中脱节/否认问题轮）· TF-CNF-03[嗯] 共享轮
Verification: 真实模型运行（GLM Coding Plan 入口）重点子集全部通过解释口径 4.4 节判定——回答引用当前待确认单、不否认业务、无新增资金动作；证据 gzip + 摘要归档；不得用离线通过替代
Owner: Erwin
Directory: 运行与证据归档（不改运行代码；证据按 evals 运行台账既有格式落对应 evidence 目录）
Status: done（2026-10-12 执行完成：18 轮真实模型复验 + 功能侧共享轮；证据归档并登记台账，安全线移交信号已发出，Issue #84 关闭）
Blocked by: None —— [01 票](01-planner-context.md)已于 2026-10-12 合入（PR #95/#96）；[03：确定性短路](03-deterministic-shortcut.md) 若被采纳则一并等待
Source issue: [Issue #84](https://github.com/DrErwin/hackerthon-bank-agent/issues/84)
Note: 本票复验结论同时是 [03 票](03-deterministic-shortcut.md) 的 YAGNI 门——基线复验全绿则 03 关闭为「不需要」，仍有余留问题才采纳 03。

## 任务

1. 01 票合入后，用真实模型跑重点子集：SEC-C-001 问题变体若干轮 + TF-CNF-03[嗯] 共享轮，按[用例正文 4.4 节](../../../evals/security/安全评测集-v0.1-2026-10-07.md)解释口径人工复核——修复前 11 轮脱节、2 轮否认业务的形态不再出现。
2. 证据归档与台账登记沿用 evals 运行报告规范（gzip + 摘要 + sha256）；安全侧证据落位与台账格式遵循 `evals/security/` 现行口径，必要时与安全线对齐。
3. 移交：通知安全线（Ringo / PM 代行的 [v04-security/01](../../v04-security/packages/01-detector-and-coverage.md)）启动全量转正复跑——SEC-C-001 余 14 轮 + 33 轮 gated，窗口 10-16～10-18。
4. 收口：[Issue #84](https://github.com/DrErwin/hackerthon-bank-agent/issues/84) 留证关闭（01 的 PR 链接 + 本票复验证据）；项目跟踪底座行更新。

## 完成判据

- [x] 重点子集真实运行证据归档且解释口径全部合格——SEC-C-001 六变体×3（18 轮）真实模型运行：0 Failed、断言全过、零资金动作；§4.4 逐轮复核 **18 符合 / 0 不符合 / 0 证据不足**（`evals/security/evidence/2026-10-12/`）
- [x] 功能侧共享轮：`TF-CNF-03[嗯]` 三轮真实模型运行均 Passed（19/19 断言、零资金动作、回复引用待办并说明聊天不算确认），归档于 `evals/transfer/evidence/2026-10-12/`
- [x] 安全线收到移交信号（[run-log 备注](https://github.com/DrErwin/hackerthon-bank-agent/blob/main/evals/security/run-log.md) + [Issue #86 回帖](https://github.com/DrErwin/hackerthon-bank-agent/issues/86)）
- [x] [Issue #84](https://github.com/DrErwin/hackerthon-bank-agent/issues/84) 留证关闭

## 执行记录（2026-10-12）

- 入口与模型：GLM-5.3 @ Coding Plan（`.env.local-demo.json` 当前配置；10-10 基线为 GLM-4.7，模型差异已在台账如实标注，历史报告未改）。
- 首次真跑 15 Failed：根因是评测缝未跟上 01 票的接口变更（[#05](05-eval-seam-context-summary.md)：`RecordingPlanner` 旧五参签名，等待期回合 TypeError、真实模型从未被调用），非修复失效；同缺陷在 API 测试替身存在（[#06](06-api-planner-double.md)）。该次报告保留为缺陷证据（`…18rounds-seam-broken.json.gz`）。
- 修好评测缝后重跑（提交 `c441a7d`）：18 轮 0 Failed / 18 Blocked（解释缺口）、逐轮回复引用当前待确认单；§4.4 判定后 18 轮解释缺口清零。
- 结论：03 票（确定性短路）按 YAGNI **不采纳**——基线复验全绿，等待期应答已由受控上下文满足。
