# 01：已采用个人预算持久化与改版

Ticket ID: v05-adopted-budget-storage/01

Package: [v05-cross-linkage/packages/01-platform-bank：公共接缝与模拟银行](../../v05-cross-linkage/packages/01-platform-bank.md)

Spec: [已采用个人预算持久记录](../spec.md)

Type: 开发

Owner: Erwin

Directory: `backend/app/storage/`

Status: in_progress

Accepted by: Erwin（中控委派本执行对话）

Accepted at: 2026-10-25

Blocked by: None（公共模型及既有占用接口已在 main）

## What to build

落实现行 AdoptedBudget：受控持久采用、active/superseded 连续改版、来源任务与交互身份、准确引用和隔离候选读取、重开恢复。保留现有预算占用接口；业务匹配和额度判断留给 cross。

## Acceptance criteria

- [ ] S01：真实落库、默认只列 active、准确引用/含历史读取、重开恢复。
- [ ] S02：改版原子替换、明确旧版本、旧占用不丢；重复/跳号/过期改版拒绝。
- [ ] S03：交互重放幂等、异参冲突、旧请求重放不激活 superseded。
- [ ] S04：可信 user/round 与来源任务核对、任务版本守卫、跨主体/轮次拒绝。
- [ ] S05：独立连接并发采用/改版，只产生一个新版本，无半更新。
- [ ] S06：v5 迁移保留旧数据、初始化幂等、新轮次隔离。
- [ ] 记录局部/全量实际验证、双轴独立审查、cross 调用样例与边界。
- [ ] 创建并附加代码 PR，交中控排队；不合并、不改共享状态、不代签真人。

## Comments

2026-10-25：中控明确授权按本独立组单票推进规格、实施及审查。与原生日业务票的顺序依赖由中控维护，本票仅更新自己的记录。
