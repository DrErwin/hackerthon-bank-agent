# v0.3 Erwin 纵向后端实施规格

Status: ready\
Owner: Erwin\
Milestone: v0.3.0 普通转账纵向链路\
Source package: [交付包 01：v0.3 纵向后端主链路](../transfer-agent-framework/packages/01-vertical-backend.md)\
Scenario: [普通转账驱动的 Agent 框架纵向场景](../transfer-agent-framework/spec.md)

## 目标

按冻结契约完成第一条真实后端链路：用户请求进入主 Harness，普通转账子图推进，在确认和验证处暂停，经过最小安全门调用模拟银行，并能恢复、查清结果和回放全过程。

## 拆票边界

- 本实施包只拆 Erwin 当前承担的后端、模拟银行评测和最终收口工作。
- 每张实现票只修改 `Directory` 指定的一个目录；跨目录依赖通过公共契约连接。
- `security/` 和 `modules/transfer/` 是 v0.3 临时实现，分别由 Ringo、梁爽审查，阶段后回到长期负责人。
- 票据只固定业务结果、边界和验收，不提前指定不必要的内部类、文件或抽象。
- 发现冻结契约确有缺口时另开契约问题，不在实现票中顺手改变公共语义。

## 推进顺序

```text
01 后端工程骨架
  └─ 02 公共契约代码
       ├─ 03 运行存储
       │    ├─ 04 模拟银行与接入层
       │    ├─ 05 审计回放
       │    └─ 06 记忆与上下文
       ├─ 07 最小安全门
       └─ 08 普通转账参考子图（可先用 stub）
             └─ 09 主 Harness 集成
                   └─ 10 API 与事件流

11 模拟银行评测可提前编写，04 完成后跑真实实现。
12 联合验收等待前后端与各方评测就绪后执行。
```

同一时间最多保留两个未合 PR。能用冻结契约和 stub 独立验证的票可以提前开发，真实集成仍按依赖顺序收口。

## 票据清单

| 票 | 目录 | 当前状态 | 完成后解锁 |
|---|---|---|---|
| 01 后端工程骨架 | `backend/` | ready | 02 |
| 02 公共契约代码 | `backend/app/contracts/` | blocked | 03、07、08 |
| 03 运行存储 | `backend/app/storage/` | blocked | 04、05、06 |
| 04 模拟银行与接入层 | `backend/app/services/` | blocked | 真实银行联调、11 实跑 |
| 05 审计与回放 | `backend/app/audit/` | blocked | 09、10 |
| 06 记忆与上下文 | `backend/app/memory/` | blocked | 09 |
| 07 最小安全门 | `backend/app/security/` | blocked | 08、09 |
| 08 普通转账参考子图 | `backend/app/modules/transfer/` | blocked | 09 |
| 09 主 Harness 集成 | `backend/app/agent_platform/` | blocked | 10 |
| 10 API 与事件流 | `backend/app/api/` | claimed（09-30 Codex 执行，工程增量经独立 AI 审查并由 PR #25 合入；验收未完成，公共能力缺口见票据） | 前端真实联调、12 |
| 11 模拟银行评测 | `evals/mockbank/` | ready | 12 的银行证据 |
| 12 v0.3 联合验收与收口 | `docs/versions/v0.3.0/` | blocked | v0.4 启动判断 |

## 本实施包完成标准

- 01—11 的实现与评测票完成并合入。
- 前端、安全评测和转账评测已达到可联合运行状态。
- 12 对 AF01—AF14 给出可重复的通过证据，或如实记录未通过项。
- `docs/versions/v0.3.0/completion.md` 已记录实际结果；未通过时不得启动 v0.4 实现。

## 原契约缺口补票（2026-09-30）

票 10 API 接入时登记的 #23 新会话恢复、#24 无业务意图仅回复，已补建 [独立规格与六张实施票](../v03-session-recovery-reply/spec.md)。它们属于原契约 §6.3 / §6.4 的未完成项，不改变本阶段范围；原十二张票保留编号，补票独立编号避免混同 GitHub Issue。仅完成补票，未开始实现，票 10 / 12 与阶段验收仍未完成。
