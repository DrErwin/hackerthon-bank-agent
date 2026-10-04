# 交付包 03：v0.3 评测与专业审查

Status: in_progress\
Owner: Ringo（安全）、Erwin（转账〔09-28 起〕、模拟银行与端到端）\
Activation: Erwin 已于 2026-09-27 确认，可按冻结规格立即拆票\
Start when: 规格与契约已冻结；实现未完成时先写可执行用例和 stub 适配\
Spec: [普通转账驱动的 Agent 框架纵向场景](../spec.md)

Accepted by: Erwin（转账业务评测与端到端实跑，2026-10-03；Ringo 安全工作线待记录）\
Accepted at: Erwin 2026-10-03；Ringo 未记录\
Work spec: Erwin [普通转账评测规格与工作组](../../v03-transfer-evals/spec.md)；Ringo 待建立或关联

领取与执行按[队员开工规范](../../../docs/agents/delivery-workflow.md)：明确接受后 AI 自动登记包与项目跟踪，检查通用 Skill，再按 `to-spec → to-tickets → 按票执行` 推进；已有规格和票直接续做，有评测代码开发时使用 `implement`。

## 业务目标

让各专业负责人不用等待 Erwin 写完全部代码，就能先定义“什么算通过”，并在真实接口出现后持续验证。

## 分工

| 工作 | 负责人 | 本期结果 |
|---|---|---|
| `evals/security/` | Ringo | 权限、确认、验证、阻断、跨用户、注入、秘密不落盘及正常放行用例；审查 Erwin 的最小安全实现 |
| `evals/transfer/` | Erwin（09-28 会定接手） | 对照 PRD T01—T18 与场景 AF01—AF10 的转账业务用例；审查 14 步流程是否走样 |
| `evals/mockbank/` | Erwin | 银行返回、防重复、结果查询、故障和恢复用例 |
| 端到端验收编排 | Erwin | 串联真实 Harness、安全入口、转账、银行和前端，执行 AF01—AF14 |

## 协作方式

- 评测负责人现在即可拆票，不需要等待后端票全部拆完。
- 先按冻结契约写输入、预期结果和通过标准；真实接口就绪后替换 stub 并运行。
- 发现实现不符合规则时，由实现所在目录的票修复，不在 `evals/` 复制业务逻辑。

## 验收

- 正常路径和关键失败路径都有明确、可重复的判定。
- 安全评测同时证明“该拦的拦住”和“正常交易能通过”。
- 转账评测引用 PRD，不重新发明业务流程。
- 评测结果能够成为 v0.3 `completion.md` 的完成证据。

### 2026-10-05 追加工作领取与交付

Accepted by: Erwin（本次仅修复票12，用户明确批准实施）\
Accepted at: 2026-10-05\
Work spec: [v03-transfer-eval-fixes修复规格](../../v03-transfer-eval-fixes/spec.md)

当前票implemented、独立PR待审查/合入；完整包仍in_progress，不改为accepted，不恢复模型10。详见[诊断与交付记录](../../v03-transfer-eval-fixes/online-diagnosis-20261005.md)。
