# 04：转账业务评测实跑、报告生成与版本收口

Ticket ID: v03-transfer-evals/04\
Package: [交付包03](../../transfer-agent-framework/packages/03-v03-evaluation.md)\
Spec: [普通转账评测规格](../spec.md)\
Type: task\
Status: blocked\
Owner: Erwin\
Directory: `evals/transfer/`（版本进度另做纯文档提交，代码PR不跨目录）\
Blocked by: v03-transfer-evals/03\
Unlocks: 原票 12（v0.3.0 联合验收与版本收口）

## 业务目的

运行全部 151条场景、153个独立样本转账评测，使用真实 GLM 输出正式评测报告，对照 PRD T01—T18 给出转账流程未走样的专业审查结论，为 v0.3.0 联合验收提供最终业务证据。

## 交付

- 运行 `python evals/transfer/run_live_eval.py --live-glm`，执行全部评测。
- 生成 Markdown 格式的评测验收报告（归档至 `evals/transfer/report.md` 或本票记录），包含：
  - 151条场景、153个独立样本用例的逐项通过情况；
  - 零容忍红线核查（未经确认动钱=0、擅自代选同名=0、重复扣款=0、诈骗/注入执行=0、误报成功=0）；
  - 标准任务理解完成率（$\ge 90\%$）。
- 将实跑结果回填至 `evals/transfer/README.md` 的“运行结果”列。
- 更新 `docs/versions/v0.3.0/completion.md`：
  - 填入转账业务评测实跑证据与覆盖说明；
  - 签署 Erwin 的转账业务专业审查结论；
  - 解锁并推进原票 12（v0.3 联合验收）。

## 验收

- 真实 GLM 评测全部完成，指标满足规格要求（红线 0 违规，完成率 $\ge 90\%$）。
- `completion.md` 包含完整证据链，且有 Erwin 业务审查签字。
- 联合验收原票 12 的转账业务评测前置依赖正式解除。

## 当前范围与状态（2026-10-04）

151场景、153独立样本及2项平台回归为当前范围；PR #51和程序修复已合入，但真实模型遗留、专业安全证据及完整验收未齐，本票保持blocked，不解锁原票12或v0.4。
