# v0.4 Ethan 账单公共业务评测 · 票 06（阶段一）

这是一张**实际可执行**的 L01 公共业务评测增量，不是全部 BF01—BF07 验收。测试直接经过真实 Harness、账单 Entry、权限执行器、B01/B08、SQLite 检查点和虚构种子银行；规划器和授权/风险输入明确是测试替身，不能推定生产安全、真实模型、HTTP 或 React 已验收。

- [场景清单与验证点](public-business-cases.md)：17 个独立 L01 业务场景，覆盖本人账户、消费/退款/转账、餐饮明细、澄清、取消、幂等、银行取数故障及跨会话恢复。
- [机器清单](public-business-cases.json) 和 [业务测试](test_public_business_eval.py) 逐 ID 对齐；[固定源码运行器](run_business_evidence.py) 检验完整 checkout 中的源文件 Git Blob，并拒绝缺失源文件或银行结果篡改。
- [本轮运行台账](run-log-public-06.md)：区分源码固定提交、原始报告、历史运行和最新 CI。
- 旧 2026-10-19 17/17 实跑记录仍在原分支 `test/bills/public-business-evidence-06`。那是历史源码证据，**不是本轮 main 的新通过声明**。

## 当前验收边界

本增量严格标记 `phase1 / partial`；17 个 L01 公共业务场景不等于完整的每子功能至少 10 条、每类异常至少 3 条，也不包括生产 L02/L03、报告导出、真实模型、页面和专业安全。正式整票是否达标，必须另在 BF01—BF07 统一覆盖表和联合验收中判定。

### 运行

在仓库根目录、安装 `backend[dev]` 后：

```bash
python -m pytest -q evals/bills/test_public_business_eval.py
python evals/bills/run_business_evidence.py --revision "$(git rev-parse HEAD)"
```

第二条对固定的实际源码提交运行并生成不覆盖旧文件的 gzip；随后将报告和 SHA256 归档。不得把当前分支的旧报告贴到新 SHA。
