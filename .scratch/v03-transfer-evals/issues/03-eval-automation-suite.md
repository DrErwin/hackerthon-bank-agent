# 03：转账自动化评测套件与 Live GLM Runner

Type: task\
Status: in_progress\
Ticket ID: v03-transfer-evals/03\
Package: [transfer-agent-framework/packages/03-v03-evaluation：v0.3评测与专业审查](../../transfer-agent-framework/packages/03-v03-evaluation.md)\
Spec: [普通转账评测规格](../spec.md)\
Owner: Erwin\
Directory: `evals/transfer/`\
Blocked by: v03-transfer-evals/01、v03-transfer-evals/02\
Unlocks: 04

## 业务目的

将 01 规划的 151条场景、153个独立样本转账用例实现为可执行、数据驱动的自动化评测套件，并提供双轨运行支持（离线快速 pytest 与真实智谱 GLM 评测），输出结构化断言。

## 交付

- 在 `evals/transfer/` 建立数据驱动评测集：
  - `cases.json`（或参数化数据源）：存储 01 规划的全部 151条场景、153个独立样本用例的结构化字段（输入、前置、预期交互、预期结果与断言）；
  - `test_transfer_eval.py`：使用 `pytest` 参数化加载用例，利用确定性 Harness 执行离线回归测试；
  - `run_live_eval.py`：评测执行脚本，支持传入 `--live-glm` 开关，连接本机真实配置的智谱 GLM-5.3（Coding Plan 入口 `coding/paas/v4`），完整执行全部用例并收集实际模型交互。
- 实现关键断言检查器：
  - 任务状态断言；
  - 交互类型断言（如 `choose_payee`、`waiting_input` 等）；
  - 资金副作用断言（检查模拟银行数据库，确认扣款流水严格为 0 或 1）；
  - 敏感信息脱敏断言（检查运行事件日志与回执）。
- 仅修改 `evals/transfer/` 目录。

## 验收

- 离线模式：运行 `pytest evals/transfer/`，151条场景、153个独立样本测试在秒级内全绿通过。
- 在线模式：运行 `python evals/transfer/run_live_eval.py --live-glm` 能正常连接真实模型，逐条记录真实意图抽取结果，无崩溃异常。
- 独立 PR，通过仓库静态检查与双轴 AI 审查。


## 2026-10-04 执行补充

用户明确要求在新对话完成票03。完整票号 `v03-transfer-evals/03`，续用本组spec及交付包03。前置01 PR #48、02 PR #50均已合入（02主线提交 `baca81233e725ee1d1d47fa8020a8acb5ff4221d`），实现依赖已满足。

当前范围以 `evals/transfer/cases.md` / `fixtures.md` / `README.md` 为准：151条场景、153个独立样本、2项平台回归引用及7项编号迁移；旧40+不是执行上限。数据D1及A6/A8_ACC已由02提供，隔离库调用 `seed_demo(include_evaluation=True)`；closed、类别、实际历史额度及故障前置由03复用真实存储/服务测试接缝，禁止复制银行规则。证据不可用按Blocked报告，不伪造全绿或真实模型结论。代码只在 `evals/transfer/`，过程记录另行更新；真实GLM、离线替身、浏览器层证据明确区分，票03不自动收口04或联合验收12。

## 2026-10-04 开工记录

Codex（Erwin工作线）按用户授权使用implement，在独立managed worktree实施，分支codex/transfer-eval-suite，基线baca81233e725ee1d1d47fa8020a8acb5ff4221d。只改evals/transfer代码；过程记录单独保留。151场景/153样本全范围，未授权合并、不启动04或原12收口。

## 2026-10-04 实现交付及验收状态

[PR #51](https://github.com/DrErwin/hackerthon-bank-agent/pull/51)，独立ready PR，提交58740f541a6777f87490593a91515e4a2efda28a，未合并。实现及数据/失败原始证据只在evals/transfer/，主工作区其他改动未触碰。

完整151场景/153样本、三种执行层、两项当前平台回归引用已实现。离线真实流程完整运行136 Passed / 16 Failed / 1 Blocked；pytest总138 passed、16 failed、1 skipped（包含目录检查与平台回归）。真实GLM完整运行126 Passed / 23 Failed / 4 Blocked，无评测器Error。标准分母21/21；真实缺项追问6/9，未达到100%。5条真实React故障用例和2项平台回归通过，后端/MockBank既有287回归通过。最后QRY03/RCV22覆盖修正后定向离线及真实GLM各2 Passed，单独保留对应源码指纹，不混称全量已在最后源码重跑。

Standards、Spec独立AI审查首轮漏检已修复，最终复审通过；不是Ringo本人安全审批或Erwin业务签署。首次失败、历史评测器Error及全部完整/定向报告保留，报告中没有API Key、验证码或完整专用号码原文。业务缺口见[PR问题记录](https://github.com/DrErwin/hackerthon-bank-agent/blob/codex/transfer-eval-suite/evals/transfer/gaps.md)：验证终止/技术故障状态、基础验证跨任务复用、回查过期任务快照、手动户名不匹配状态、完整专用卡号进入普通checkpoint_blobs/checkpoint_writes以及实际模型的模糊输入/缺项问题。跨目录问题只记录，未越界修复；Ringo真实攻击来源缺证据Blocked，专业安全NotRun，红线Unverified。

本地语法、链接、差异空白检查通过；PR当前提交58740f5的[Repository checks运行](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/37142122774)已success（2026-10-03 17:54:38 UTC）。当前CI只测后端/MockBank，不证明153评测全绿。原“秒级全绿”尚未达到（本机完整pytest309.24秒且有真实失败），因此本实施票维持in_progress，不伪标resolved，不进入04，也不收口原12/v0.3。


## 2026-10-04 本轮合入补充

用户已豁免本轮Ringo审批并授权合并，[PR51](https://github.com/DrErwin/hackerthon-bank-agent/pull/51) 已合入 `86b158eb9db94d9b4352ab1262bea54d7f571f0d`；后续程序修复与口径修正01—09也已合入。主线 `a8218ffd2fdb777a9c9382bed9f3ff5cd3f29524` 离线153样本147 Passed/6 Blocked、0 Failed/0 Error。此票工程套件已合并，真实GLM仍有历史未解决结果，原全绿验收条件未全满足，维持in_progress；04及原12仍blocked。不将本轮审批豁免记为Ringo本人审查。

## 仓库同步核实（2026-10-04）

[PR #51](https://github.com/DrErwin/hackerthon-bank-agent/pull/51)已合入`86b158e`，程序修复01—09已合入。主线153离线147 Passed / 6 Blocked、0 Failed / 0 Error；真实模型遗留及完整通过条件仍未满足，本票保持in_progress。此前PR待合状态为历史，详见[版本完成情况](../../../docs/versions/v0.3.0/completion.md)。
