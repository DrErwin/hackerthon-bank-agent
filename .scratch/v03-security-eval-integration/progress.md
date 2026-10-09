# 安全评测接入实施记录

更新：2026-10-09（三票已由用户批准合入 main）。用户授权 AI 实施，不代表 Ringo 本人领取、专业签核或 v0.3 联合验收。

## 任务图与边界

01 程序安全评测 → 02 联合执行与证据共用 → 03 真实模型入口与报告。代码只改 `evals/security/`；每票独立分支和 PR，后继 Draft PR 指向前序分支。本地 `codex/security-eval-integration` 用于汇集验证，不创建替代三票的总 PR。

接缝沿用[规格](spec.md)确认的真实 API、安全执行器和独立 MockBank 操作/账本，测试不复制银行规则。2026-10-08 及之前子代理由 Codex 编排（spawn 显式 gpt-6-luna / max）；2026-10-09 实施轮由 DSH 子代理完成，其 spawn 不提供型号与推理强度参数。

## 当前状态

| 实施票 | 状态 | 证据 |
|---|---|---|
| [01 程序安全评测](issues/01-program.md) | completed | [PR #80](https://github.com/DrErwin/hackerthon-bank-agent/pull/80) squash 合入 `3ca78be`；双轴AI审查完成 |
| [02 联合执行与证据共用](issues/02-joint.md) | completed | [PR #82](https://github.com/DrErwin/hackerthon-bank-agent/pull/82) squash 合入 `86b2ba4`；离线基线 19/1/288/1 保持 |
| [03 真实模型入口与报告](issues/03-live.md) | completed | [PR #83](https://github.com/DrErwin/hackerthon-bank-agent/pull/83) squash 合入 `c840c88`；57轮默认离线 0/0/57 |

三票均于 2026-10-09 由用户（项目负责人）明确批准合入；Ringo 专业签核未发生，以规格"用户明确豁免"条款记录。合入后 main 上 50 项测试全绿。

## 已核对的证据

- 最新规格基线 `90560ca`；启动记录经纯文档提交发布 `87d8ff6`。Git receive-pack 返回服务端错误，改用 GitHub Git Data 接口，逐文件 blob 与完整 tree 摘要一致；无强推。主工作区未切分支或改文件。
- 七份安全来源文档的 blob 摘要与当前 main 一致。原118主用例、253参数实例、309历史模板不修改。
- 完整功能离线基线：153样本，147 Passed / 6 Blocked / 0 Failed；标准21/21，缺项8/8，额外平台回归2/2。五个React观察未启用，TF-VFY-16专业材料待；红线汇总仍Unverified，不作全集验收。
- 本期真实计划保留19安全实例57轮、35功能样本37轮、共享3轮，共53样本91轮。现有业务链可继续接入D002、C001六变体、P002共8实例24轮（含共享3轮）；其余11实例33轮需实际检测、资料入口或业务/攻击观察能力。P002独立初始余额200000分，不能共享功能的不同余额夹具。
- 本次未读取真实模型配置、未调用付费模型；离线替代、页面、检测器及专业审查分别记录。
- 2026-10-09 三票全部交付并完成集成分支双轴AI审查（Standards/Spec 并行子代理）。修复提交 a5ba300/aacee87：audit_events/security_confirmations 改走 admin 审计时间线与运行时确认入口、银行三表 SQL 收敛唯一 helper（附直读原因）、两入口共用仓库外路径校验、run_suite 拒绝非空工作目录、live 供应商/型号/端点改 --config 显式配置、YAGNI 参数与重复清理。终态 50 项测试全绿；309 行离线 19/1/288/1 与 live 57 轮 0/0/57 基线均不变；集成分支 `1d07a5f`。三 PR（#80/#82/#83）已标记 ready，base 链式相接，合并顺序 80→82→83。

## 下一步

三票已全部合入 main。2026-10-09 用户指示以 GLM-4.7 完成本期真实运行：安全侧 57 轮（24 真实执行断言 99/99 通过、33 能力门拦截）与功能侧重点 37 轮（35/35 Passed + "嗯"两追加轮，红线零违规）均已执行并按[归档约定](../../evals/README.md)入库（[security evidence](../../evals/security/evidence/2026-10-09/)、[transfer evidence](../../evals/transfer/evidence/2026-10-09/)）；共享 3 轮的功能侧引用已回填至安全运行台账。剩余启用前置条件：①React 页面证据（需 frontend/dist 构建）；②Ringo live 判定断言口径复核与专业签核；③11 个缺能力实例继续调用前 Blocked，直到对应检测器/资料入口/观察端建成。另有存量问题待查：evals/transfer 离线套件 TF-INP-03 期望非法 payer 被拒、实际 Passed（与真实运行无关，建议单独开票）。版本联合验收仍走原 `v03-erwin-vertical-backend/12`。
