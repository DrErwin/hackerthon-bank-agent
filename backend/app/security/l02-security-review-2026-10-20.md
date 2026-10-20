# L02 安全准入记录

Ticket ID: v04-ringo-security/10
Source issue: [Issue #187](https://github.com/DrErwin/hackerthon-bank-agent/issues/187)
Owner: Ringo
Directory: backend/app/security/
Status: implemented，等待双轴审查、主线测试口径收口及合入

## 依据与范围

以 main d133f376675ede2551f03a7378c83ac53bdd2801 和已合 PR #183 为来源。仅增加 bills.detect_anomalies 安全侧独立快照，按 ANOMALY_MANIFEST 固定十个声明字段，沿用 bills.read 的本人读取规则；策略版本 v04-local-demo-read-2 升为 v04-local-demo-read-3。未知能力、声明漂移和越权作用域继续拒绝，L01/L03 行为保持，未修改公共契约或业务流程。

平台生产注册仍由 Erwin 的 #123 负责。本分支只在测试中显式注册 L02，脚本规划器不构成真实模型或页面证据。声明冻结 #164 及真实检测器 #169 属其他分支，本增量独立于它们。

## 离线验证

新加 23 项安全测试，含全字段漂移以及嵌套权限替换；业务对象原地修改后，原固定声明仍获准，变更后的对象拒绝。真实 Harness、持久化恢复与 F10 选项适配接至安全门和模拟银行，验证选择候选后重新核对、重复请求沿原交互、零资金操作，并对照账户表、操作表及流水表完全一致。

首轮定向 95 passed / 1 failed。失败属于新增测试对 Harness 恢复顺序的预期错误：当前平台先重新检查公开能力，过期轮次抛 ACCESS_DENIED，私有门尚未到达。保留该事实，将用例拆为两个参数，分别验证公开准入先拒绝，以及显式隔离公开准入后的私有门独立拒绝。返修后定向 97 passed，未修改运行时代码以迎合测试。

全安全目录与全后端结果在测试完成后补记。AI 双轴审查、远端提交与 CI 分别记录，单元测试通过不构成 L02 纵向验收或 Ringo 真人签核。

## 已知联动项

业务目录 test_anomaly_integration.py 的 test_production_policy_keeps_rejecting_the_unregistered_l02_capability 仍锁定 L02 拒绝，其前提随 #187 准入切换失效。该测试归账单负责人，需要与安全合入协调更新；本分支按目录边界保留原文件，完整回归若在此失败如实登记。
