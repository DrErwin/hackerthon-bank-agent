# v0.4 Ethan 账单公共业务评测 · 票 06（阶段一）

这是一张**实际可执行**的 L01 公共业务评测增量，不是全部 BF01—BF07 验收。测试直接经过真实 Harness、账单 Entry、权限执行器、B01/B08、SQLite 检查点和虚构种子银行；规划器和授权/风险输入明确是测试替身，不能推定生产安全、真实模型、HTTP 或 React 已验收。

- [场景清单与验证点](public-business-cases.md)：17 个独立 L01 业务场景，覆盖本人账户、消费/退款/转账、餐饮明细、澄清、取消、幂等、银行取数故障及跨会话恢复。
- [机器清单](public-business-cases.json) 和 [业务测试](test_public_business_eval.py) 逐 ID 对齐；[固定源码运行器](run_business_evidence.py) 检验完整 checkout 中的源文件 Git Blob，并拒绝缺失源文件或银行结果篡改。
- [本轮运行台账](run-log-public-06.md)：区分源码固定提交、原始报告、历史运行和最新 CI。
- 旧 2026-10-19 17/17 实跑记录仍在原分支 `test/bills/public-business-evidence-06`。那是历史源码证据，**不是本轮 main 的新通过声明**。

## 当前验收边界

本增量严格标记 `phase1 / partial`；17 个 L01 公共业务场景不等于完整的每子功能至少 10 条、每类异常至少 3 条，也不包括生产 L02/L03、报告导出、真实模型、页面和专业安全。正式整票是否达标，必须另在 BF01—BF07 统一覆盖表和联合验收中判定。

## 证据绑定与 CI 边界

- 归档 [20261020T125347038226Z-python3.12.15-public-l01-phase1-c2e8f3ea2949.json.gz](evidence/2026-10-20/20261020T125347038226Z-python3.12.15-public-l01-phase1-c2e8f3ea2949.json.gz) 绑定受测源码 [`c2e8f3ea2949c32bf4526b426f647e6c03f69f5c`](https://github.com/DrErwin/hackerthon-bank-agent/commit/c2e8f3ea2949c32bf4526b426f647e6c03f69f5c)，由一次性 [Actions #39425788637](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/39425788637) 真实生成；报告二进制未改写，执行时间与逐样本结果均来自该次运行。
- 本 PR 头的 Repository checks 只跑 967 条 backend 测试与 14 条 MockBank 测试，不重跑这 17 条 L01 业务用例；backend/MockBank 绿色不等于本评测通过，17 条只认固定源码 runner 的原始报告。
- 复现必须在受测提交上执行：在原提交 `c2e8f3ea…`（LF 检出）用原 runner，或在任意 LF 检出用 `--revision <已发布提交>`，或使用本 PR 修复后的 runner 在 Windows `core.autocrlf=true` 下用 `--revision <包含该 runner 的已发布提交>`。runner 先把文本源的 CRLF 规范化为 LF 再比对 Git blob；工作树任一源文件（包括 runner 自身）与 pin 的提交不一致时，会在测试前拒绝执行。
- 本 PR 已在修复提交 [`efd9bfe647eb57bc50dfe3d58324653994d044cf`](https://github.com/DrErwin/hackerthon-bank-agent/commit/efd9bfe647eb57bc50dfe3d58324653994d044cf) 上用 Windows + `core.autocrlf=true` 重生成[新报告](evidence/2026-10-20/20261020T144141888167Z-python3.12.3-public-l01-phase1-efd9bfe647eb.json.gz)：133/133 个源文件为 CRLF，报告 `crlf_normalized=true`，17/17 通过。原 Actions 报告保留，不覆盖、不改 hash。新报告的 `pytest_args` 只含 `--rootdir .`，不再写入 CI 绝对路径。

### 运行

在仓库根目录、安装 `backend[dev]` 后：

```bash
python -m pytest -q evals/bills/test_public_business_eval.py
python evals/bills/run_business_evidence.py --revision "$(git rev-parse HEAD)"
```

第二条对固定的实际源码提交运行并生成不覆盖旧文件的 gzip；要求工作树与 `--revision` 指定的提交一致（含 runner 自身），否则拒绝执行。文本源按 UTF-8 解码，并把 CRLF 规范化为 LF 后再比对 Git blob 与计算 SHA256，因此 Windows `core.autocrlf=true` 检出也可复跑；报告会记录 `crlf_normalized` 标志及逐文件 `worktree_sha256`/`worktree_bytes`。生成后按 SHA256 归档，不得把当前分支的旧报告贴到新 SHA。
