# 02：联合执行与证据共用

Ticket ID: v03-security-eval-integration/02
Package: [交付包03](../../transfer-agent-framework/packages/03-v03-evaluation.md)
Spec: [安全评测接入规格](../spec.md)
Type: 开发
Owner: 用户授权AI接入；Ringo专业审查待记录
Directory: evals/security/
Status: completed（用户批准合入 2026-10-09；Ringo 专业签核未发生，以用户明确豁免为准）
Blocked by: None（01已交付PR #80；依赖代码仅汇入本地integration，尚未合入main）
Core scenarios: SI06
Verification: 本票自动断言、故障及缺口反例、相关离线流程；联合验收仍归原票12。
Accepted by: 用户授权AI
Accepted at: 2026-10-07

## What to build

同次运行关联功能与安全编号，先核对兼容条件，再用独立安全断言判定；缺证据Blocked，突变反例不能Passed。

## Acceptance criteria

- [x] 同次运行关联功能与安全编号，先核对兼容条件，再用独立安全断言判定；缺证据Blocked，突变反例不能Passed。
- [x] 不修改原JSONL、历史模板或后端业务规则；本票代码只落evals/security/。
- [x] 保存真实执行与离线替代边界；未调用付费真实模型，Ringo审查单列。
- [x] 本票专项及受影响核心路径验证、有独立分支/PR和双轴AI审查证据。

## Comments

2026-10-09 用户（项目负责人）明确批准本批 PR，squash 合入 main（#82 → `86b2ba4`；squash 分叉产生的 add/add 冲突经 5c9a875 merge 解决，合并后 37/0 复验通过）。Ringo 专业签核未发生，以用户明确豁免记录。本票关闭。

2026-10-09 联合执行已交付 [PR #82](https://github.com/DrErwin/hackerthon-bank-agent/pull/82)，代码提交 4485dd3，base 指向 01 分支。37项专项测试通过（终态50，含审查修复新增）；联合语义：同次隔离实际运行关联 TF-CNF-03[嗯] 与 SEC-C-001/v03，先核对兼容条件再独立判定，篡改证据→双Failed、缺失证据→Blocked、外部Passed不被继承。309行离线报告保持 19 Passed / 1 Failed / 288 Blocked / 1 PENDING_SPEC 基线。双轴AI审查发现的入口约束与YAGNI问题经修复提交 a5ba300/aacee87 解决并进入 PR 链。待 Ringo 专业批准。

2026-10-08 用户的新会话实施授权有效；01已完成代码交付，AI按依赖顺序启动本票。独立分支/PR仅改evals/security/；后继Draft PR以01分支为base，不调用付费模型，专业审批单列。

2026-10-07本轮只交付规格与票据。用户明确要求“只执行到拆票，实施先不做”；本票未领取实施，未写代码、未运行评测。实施须等待用户后续明确启动及前置票交付。
