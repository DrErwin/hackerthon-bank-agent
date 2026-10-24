普通转账原有151条场景尚无完整可执行评测。本PR将八字段矩阵展开为153个独立样本，提供离线pytest与真实GLM-5.3 Coding Plan runner；二者执行真实流程、安全门、网关和隔离模拟银行，报告逐条保留模型交互、确认/验证、原操作恢复、资金调用、账本及失败断言。TF-CNF-03的“嗯/好/行”分别运行；5条事件/旧响应故障使用真实React与TCP HTTP，另取2项当前平台回归证据。

本地实施票：**v03-transfer-evals/03：转账自动化评测套件与Live GLM Runner**，`.scratch/v03-transfer-evals/issues/03-eval-automation-suite.md`（本地过程文件，未入库）。规格依据：[当前八字段矩阵](https://github.com/DrErwin/hackerthon-bank-agent/blob/codex/transfer-eval-suite/evals/transfer/cases.md)、[前置与范围](https://github.com/DrErwin/hackerthon-bank-agent/blob/codex/transfer-eval-suite/evals/transfer/README.md)。Depends on PR #48 and PR #50（均已合入，基线baca8123）。仅修改`evals/transfer/`，覆盖AF01—AF14设计映射；不更改安全实现、银行规则或公共契约，不代签Ringo专业安全结论。

实际验证与限制：

- 离线完整153样本：136 Passed / 16 Failed / 1 Blocked；pytest合计138 passed、16 failed、1 skipped（另有目录检查及平台回归）。真实GLM完整153样本：126 Passed / 23 Failed / 4 Blocked。均没有评测器Error，Failed如实使命令非零退出，没有xfail或调整期望制造全绿。
- 冻结标准任务21/21通过；真实GLM缺项追问6/9，未满足100%。5条实际React场景及2项平台回归通过。受控风险事实、故障和时钟均标注替身；TF-VFY-16缺Ringo真实攻击来源Blocked，专业安全NotRun，红线结论Unverified。
- 全量运行后强化QRY03自动回查中摘要/原截止及RCV22原操作号断言，两项定向离线、真实GLM均Passed；各源码指纹及全量/定向结果分别保留，未覆盖首次失败或混称全量在最后修正代码运行。
- 后端与模拟银行回归287 passed；既有前端构建通过；评测器Python语法、文档链接及差异空白核对通过。当前仓库CI只测试后端/模拟银行，不代表153评测通过。完整pytest309秒，原票“秒级全绿”尚未达到。
- Standards与Spec两条独立AI复审通过，首次发现的评测漏检已修复；这不是人类业务审批或Ringo个人批准。

[完整实现/实跑证据](https://github.com/DrErwin/hackerthon-bank-agent/blob/codex/transfer-eval-suite/evals/transfer/automation-evidence.md)与[跨目录问题记录](https://github.com/DrErwin/hackerthon-bank-agent/blob/codex/transfer-eval-suite/evals/transfer/gaps.md)列出验证码终态、基础验证跨任务复用、登录过期状态、专用卡号进入普通检查点等产品问题。原始逐样本JSON无损压缩、脱敏留存，API Key未入库。

**本PR可审查；产品评测未通过，票04、原12及v0.3未收口。未授权合并。**


### 本轮合并授权（2026-10-04）

用户明确指示：“我豁免ringo审批，合并吧”。本 PR 属于本轮转账评测及 01—09 程序修复范围；记录为项目负责人豁免本轮 Ringo 真人审批，不记作 Ringo 已审查，不替代安全专业评测或 v0.3 最终验收。票 10 继续暂停。合并前更新到最新 main 并核验当前提交 CI。
