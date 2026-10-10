# 04：SEC-V-002 断言翻转与重跑取证

Ticket ID: v03-security-eval-integration/04
Package: [transfer-agent-framework/packages/03：v0.3 评测与专业审查](../transfer-agent-framework/packages/03-v03-evaluation.md)
Spec: [v03-security-eval-integration 规格](spec.md)
Core scenarios: 安全用例 SEC-V-002（验证码同号异内容冲突）；纵向场景 AF08/AF11 的验证幂等证据补充。
Verification: 安全评测断言与实现对齐：同 `submission_id` 异内容 → 409 冲突、原结果与计数不变、不转入待核实；新编号真实错误计数 1→2；重传只计一次；去重不含原文；银行零提交。
Owner: Ringo（按用户 2026-10-10 指示由 Erwin 代行，记录代行、不冒名）
Directory: `evals/security/`
Status: pending
Blocked by: [v03-verification-conflict-fix/02](../v03-verification-conflict-fix/issues/02-api-conflict-mapping.md)
Source issue: [Issue #79](https://github.com/DrErwin/hackerthon-bank-agent/issues/79)
Note: 本票沿用既有组 v03-security-eval-integration 的规格；只在票01/02合入后执行，不改产品代码。

## 交付

1. `test_security_eval.py::test_v002_...` 期望从"观测到 503 失败"改为"409 冲突 + 新编号计数 2"（若实现语义与断言名变化，同步说明）。
2. 重跑 `SEC-V-002` 及安全评测套件；正确行为则记录 Failed→Passed，报告按[归档约定](../../evals/README.md#六运行报告归档全模块统一)入库 `evals/security/evidence/<日期>/`。
3. 更新 `evals/security/run-log.md` 与 README 状态；#79 在对应产品修复合入后被检查关闭（不在本票自作产品修复或越权声称修复）。

## 验收（本票局部）

- SEC-V-002 转 Passed（或如实保留失败并说明）；安全评测测试全绿；
- 无新产品代码改动；资金写 0。

## Comments

- 2026-10-10：由 Issue #79 拆出，追加到既有安全评测组，等待票02冲突映射合入。