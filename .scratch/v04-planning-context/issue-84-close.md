## 关闭说明（2026-10-12）

issue 正文的两个症状（等待确认时回复脱节；否认已有业务）已修复并**真跑复验通过**：

1. **修复**：PR #95（`storage.list_session_tasks`，会话内任务列表）+ PR #96（harness 构建受控待办摘要注入规划提示；`Planner`/`DeepAgentPlanner.select` 增可选 `context_summary`）。秘密边界按 PM 代行记录（注入=状态短语 + 已打码的原请求文本；原始模型消息不落盘）。
2. **真跑复验**：GLM-5.3 @ Coding Plan 跑 `SEC-C-001` 六变体×3（18 轮）——断言全过、0 Failed、零资金动作；§4.4 逐轮复核 **18 符合 / 0 不符合 / 0 证据不足**，每轮回复都引用当前待确认的「给妈妈转500元（默认主账户A1）」并说明需在确认单完成确认、聊天回复不构成授权。功能侧共享轮 `TF-CNF-03[嗯]`×3 全 Passed（19/19 断言）。修复前 10-10 基线的「11 轮脱节、2 轮否认业务」形态未再现。
3. **复验中发现并已修的接口适配缺口**：评测缝 `evals/transfer/environment.py` 与 API 测试替身的规划器仍是旧五参签名（PR #104 已修评测缝；API 替身见 v04-planning-context/06），否则真跑会在等待期回合直接失败——首跑报告作为缺陷证据一并归档。
4. **证据与台账**：`evals/security/evidence/2026-10-12/`（18 轮报告 4D70DBC1CC7825E8、§4.4 复核 04FAD7BAEAF9027B、首跑缺陷报告 B301A86AA6C75820）、`evals/transfer/evidence/2026-10-12/`、`evals/security/run-log.md`。
5. **移交**：安全线全量转正复跑（C-001 余留轮次 + 33 轮 gated，窗口 10-16～10-18）已发信号（[Issue #86 回帖](https://github.com/DrErwin/hackerthon-bank-agent/issues/86) + run-log 备注）。
6. **可选增强结论**：确定性等待应答短路（v04-planning-context/03）按 YAGNI **不采纳**——基线复验全绿。

遗留（不属本 issue，另记）：无待办时的「最近对话」原始轮次摘要需 api 接缝（threads/messages 归 API 层），当前 User Story 8 在有待办时由摘要中的原请求文本满足。
