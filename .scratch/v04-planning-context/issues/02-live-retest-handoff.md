# v04-planning-context/02：真实运行复验与移交

Ticket ID: v04-planning-context/02
Package: PM 自拆（不开交付包）；Source issue [Issue #84](https://github.com/DrErwin/hackerthon-bank-agent/issues/84)
Spec: [v04-planning-context 规格链接](../spec.md)
Core scenarios: SEC-C-001 代表变体（v01—v06 中脱节/否认问题轮）· TF-CNF-03[嗯] 共享轮
Verification: 真实模型运行（GLM Coding Plan 入口）重点子集全部通过解释口径 4.4 节判定——回答引用当前待确认单、不否认业务、无新增资金动作；证据 gzip + 摘要归档；不得用离线通过替代
Owner: Erwin
Directory: 运行与证据归档（不改运行代码；证据按 evals 运行台账既有格式落对应 evidence 目录）
Status: open（2026-10-12 起可执行）
Blocked by: None —— [01 票](01-planner-context.md)已于 2026-10-12 合入（PR #95/#96）；[03：确定性短路](03-deterministic-shortcut.md) 若被采纳则一并等待
Source issue: [Issue #84](https://github.com/DrErwin/hackerthon-bank-agent/issues/84)
Note: 本票复验结论同时是 [03 票](03-deterministic-shortcut.md) 的 YAGNI 门——基线复验全绿则 03 关闭为「不需要」，仍有余留问题才采纳 03。

## 任务

1. 01 票合入后，用真实模型跑重点子集：SEC-C-001 问题变体若干轮 + TF-CNF-03[嗯] 共享轮，按[用例正文 4.4 节](../../../evals/security/安全评测集-v0.1-2026-10-07.md)解释口径人工复核——修复前 11 轮脱节、2 轮否认业务的形态不再出现。
2. 证据归档与台账登记沿用 evals 运行报告规范（gzip + 摘要 + sha256）；安全侧证据落位与台账格式遵循 `evals/security/` 现行口径，必要时与安全线对齐。
3. 移交：通知安全线（Ringo / PM 代行的 [v04-security/01](../../v04-security/packages/01-detector-and-coverage.md)）启动全量转正复跑——SEC-C-001 余 14 轮 + 33 轮 gated，窗口 10-16～10-18。
4. 收口：[Issue #84](https://github.com/DrErwin/hackerthon-bank-agent/issues/84) 留证关闭（01 的 PR 链接 + 本票复验证据）；项目跟踪底座行更新。

## 完成判据

- 重点子集真实运行证据归档且解释口径全部合格；
- 安全线收到移交信号（台账或项目跟踪可见）；
- Issue #84 关闭。
