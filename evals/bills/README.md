# bills 评测集

## 票06：L01 注册链路的 17 条独立业务评测（继承 #93）

- 本分支依赖评测 PR #93：新增 [17条虚构银行公共业务场景](public-business-cases.md)、[机器清单](public-business-cases.json)、可执行 [测试](test_public_business_eval.py) 与 [固定源码证据工具](run_business_evidence.py)。不把这17条算作96条全部业务设计通过。
- 历史已有 17/17 场景实跑报告（固定老源码），作为历史追溯保留。当前版本的新 CI 和新 gzip 必须在最新评测父提交上单独实跑后再标通过。真实模型、完整 L02/L03、React 和安全专业验收不在这17项覆盖内。


## 2026-10-19 23:04：L03 合入后最新主线独立实跑与原始报告

- 受测提交（对应最新含 PR #151 主线）：`49ce93a0353dcac5923e329d240eff7c7963373f`，父提交 `40a61c32e64c34f4b3872576f05a3d7fc3ee8cc7`。
- [GitHub Actions #39274554945](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/39274554945) 全仓源码检出，Python 3.12.15 / pytest 9.1.1，实际执行 `python evals/bills/run_evidence.py --revision 49ce93a0353dcac5923e329d240eff7c7963373f`。
- **147 passed / 0 failed / 0 skipped / 0 errors**；130 算术 + 17 工具，14/14 固定 Git 源码校验。
- [原始 gzip](evidence/2026-10-19/20261019T150402083715Z-python3.12.15-private-arithmetic-49ce93a0353d.json.gz)，gzip SHA256 `81b6c86671711bed31c4e9e58ca03874bd631a2580879b399dc191dd34034245`；解压 JSON SHA256 `fb67e684e7513f24b57c37e513c9c819fbd74b3fb16c5ffa9608b74488a72914`。
- 时间：UTC 2026-10-19T15:03:59.813010 → 15:04:02.079143。测试模式仅证明14个固定源文件，不证明整仓或完整 BF01–BF07 联合验收。

- 新增本归档提交仅加 gzip 与三份说明，不更动上述14个被测源码文件。早前报告作为历史证据保留，不能拿不同源码版本报告冒充本次结果。

## 2026-10-19 22:11 · 最新 GitHub 完整检出固定源码运行（本轮当前证据）

- 受测源码提交：`999c1c062cc946f89bae6607eafe6234f4f76a40`。GitHub Actions **[39266604025](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/39266604025)**：Python 3.12.15 / pytest 9.1.1，真实运行 `python evals/bills/run_evidence.py --revision 999c1c062cc946f89bae6607eafe6234f4f76a40`，无需来源切片替身。
- [原始 gzip 报告](evidence/2026-10-19/20261019T141112115688Z-python3.12.15-private-arithmetic-999c1c062cc9.json.gz)：**147 passed / 0 failed / 0 skipped / 0 errors / 0 collection errors**；按真实路径识别 **130 项算术 + 17 项证据工具**。
- gzip SHA256：`b00c8b3a961674e54c6b1d658bd54f18bc5579019522e3db66e295db9b766f47`；解压 JSON SHA256：`f18b553f3a7ebdf5b22c3f4946038e9a1603f58ffbfe82a1238ac3e57c572b6d`；`source_verification=git_object_verified_source_files`，14/14 指定源码字节与固定 Git 提交一致。
- `run_evidence.py` 只证明 **14 份指定源文件**核验，不证明全仓 Git 对象/依赖闭包/干净工作区完整性；报告归档提交不改变这14份源码。96条业务设计仍非96条全部业务通过。


负责人：周恩宇（Ethan）。对应 `v04-ethan-bills-backend/02`；本PR只修改 `evals/bills/`，只引用公共契约、不修改安全/契约/银行实现。BF01/BF03/BF05/BF06当前只有部分算术断言；BF02/BF04/BF07仍待业务实现和联调。

## 本轮交付与数量

- [核心设计](representative-cases.md)21条保持原编号；[增量设计](expanded-cases.md)79条，其中4条细化同一核心ID；去重 **96条业务设计**，不是96条通过。
- [黄金流水](fixtures/arithmetic-cases.json) **33个ARITH样本**；[机器映射](fixture_map.json)和[覆盖表双向索引](coverage-matrix.md)逐项对应真实BILL定义。BILL-STAT-24—27已补定义，不再悬空。
- 已合入#92的模块测试 **97项（65+32）**，加33个黄金样本，算术范围 **130项**。另有17项证据/编号工具测试；2026-10-19 在包含项目源码的工作树中合跑 **147项通过**；runner只核对14份指定源码与提交的 Git Blob 字节一致，不核验整树、完整依赖闭包或工作区 clean 状态，不能把工具测试混作新增业务覆盖。
- 流程以[评测指南](../README.md)为准；完整功能、故障种类和专业审查仍需后续验收。cross属于v0.5，本轮不扩展。

## 运行

仓库根目录直接执行（已通过本目录conftest加入backend，不需要手设PYTHONPATH）：

```bash
python -m pytest -q evals/bills/
python -m pytest -q backend/app/modules/bills/test_statistics.py backend/app/modules/bills/test_statistics_contract.py evals/bills/test_statistics_eval.py
python evals/bills/run_evidence.py --revision "$(git rev-parse HEAD)"
```

最后一条必须指定包含当前测试源码的40位提交，不能指向尚无这些文件的早期main。runner核对固定提交的源码，仅规范化文本CRLF/LF，其他字符变化会拒绝；每条结果记录开始/结束时间，报告写入`evidence/<日期>/`且不覆盖旧报告。

GitHub现有CI不执行本目录黄金样本，专项结果以[运行台账](run-log.md)为准。没有网络的执行环境可使用runner的`--source-manifest`文件切片模式；它必须逐文件核对已提交blob，报告会明示切片与未验证层，不能冒称整仓回归。

## 如何查一条结果

例如 ARITH-27 → BILL-STAT-24 → 公共契约§6.11。先查[覆盖表](coverage-matrix.md)，再查运行报告中的`fixture_id`、`business_case_ids`、`tested_revision`、逐样本时间与源码指纹；原核心文档的待运行指业务层，不会因算术Passed被改成完整通过。

[未验证项](gaps.md) · [运行记录与报告](run-log.md)

## 2026-10-19 16:29 实跑（14份指定源码 Git 对象核验）

- 上游审计修复 #153 合入后，立即同步当次最新 main `cd7c91ad80652852bb10fef139c2442d756ef359`。新受测源码提交为 `84b6594e0f989844f62e4c4eaad470e6f1124124`；当时工作树含589个受版本管理文件，但 runner 仅核验14份固定源文件，不代表整树核验。
- [最新原始报告](evidence/2026-10-19/20261019T082904821548Z-python3.12.14-private-arithmetic-84b6594e0f98.json.gz)：Git 对象验证模式，14/14源码指纹一致，**147 passed / 0 failed / 0 skipped / 0 errors / 0 collection errors**；另行专项 **50 passed**。解压 JSON SHA256 为 `e313bdc1de75a5b70b4c10af0bd21138b8131a65aba5c73ac3668f7491e07371`。
- 分层仍为130项算术加17项工具；50项与147项重叠。下方原运行记录与全部旧 gzip 均保留，不合并样本数、不覆盖旧证据。

## 2026-10-19 15:56 工作树实跑记录（14份指定源码核验；前序主线）

- 被测源码提交：`17031a174aed5b586032ed4c455b0c594182ab9e`，父提交为当次最新 main `9741053c304a194a4c3d5ab3048f4dbb8be3b0f9`。
- [前序原始运行报告](evidence/2026-10-19/20261019T075607860590Z-python3.12.14-private-arithmetic-17031a174aed.json.gz)：`source_verification=git_object_verified_source_files`，**147 passed / 0 failed / 0 skipped / 0 collection errors**；另跑 `pytest -q evals/bills/` **50 passed**。命令、时间、解压 SHA256 与分层统计见 [运行台账](run-log.md)。
- 96 条业务设计、33 个黄金样本、130 项算术和 17 项工具测试分别计数；本报告不证明完整 BF01—BF07 业务验收。

## 较早的同日切片证据（保留历史）

- [原始147项运行报告](evidence/2026-10-19/20261019T060007618888Z-python3.13.5-private-arithmetic-bd3c2620913e.json.gz)（`bd3c2620913ebbb1ea194a599ecf10983eb0fb79`，解压 SHA256 见 [run-log](run-log.md)）。
- 本轮执行在隔离源码切片上、经14份GitHub Blob指纹校验；runner 的 `source_verification=connector_verified_file_slice`，**不是完整 checkout 的 git_object_verified_source_files 模式**。评测设计96条不意味着 BF01—BF07 已完整通过。
