# 02：安全与功能流程共用及真实模型预算

Ticket ID: v03-joint-eval-plan/02
Package: [transfer-agent-framework/packages/03-v03-evaluation：v0.3 评测与专业审查](../../transfer-agent-framework/packages/03-v03-evaluation.md)
Spec: [功能与安全用例联合执行规格](../spec.md)
Owner: 用户授权 AI 整理；Ringo 保留安全用例归属及专业审查
Directory: evals/security/
Type: 文档
Status: resolved
Blocked by: [v03-joint-eval-plan/01：功能用例真实模型重点运行清单](01-transfer-live-list.md)
Core scenarios: J02、J03、J04，见规格
Verification: 核对功能/安全共用关系，枚举当前及后续真实模型变体，逐项核对三轮及共享扣减；现有 NOT_RUN 不变。

## What to build

把相同流程放到同一联合执行表，独立条件和观察不足保留。给出当前可跑 37 轮、待接入 54 轮和当前普通转账计划合计 91 轮；另列后续业务的 21 轮。

## Acceptance criteria

- “嗯”共用同一个真实运行记录，其他不完全相同项明确对齐条件或局部引用。
- 安全当前 11 个主用例、19 个参数实例共 57 轮，其中 3 轮与功能“嗯”共用，新增 54 轮。
- 原 e2e 28 个实例完整归类：当前 19、程序验证 2、后续业务 7。
- 固定风险、秘密扫描、真实检测与专业签核分别记录；原安全数据及结果状态不改。

## Answer

2026-10-07：交付[功能与安全联合执行表](../../../evals/security/joint-execution-plan.md)。原e2e主用例集合完整分为当前11主用例/19实例、程序验证2主用例/2实例、后续5主用例/7实例。当前57轮扣除共享“嗯”3轮，新增54轮；加功能37轮后合计91。其余相似流程注明条件、局部覆盖和缺口，不自动沿用Passed。数据、参数、重复计数及链接检查通过，原JSONL/CSV/模板未改，未执行真实模型或安全自动化。
