# 账单评测运行台账

## 2026-10-19 23:22 · 第06票最新源码 L01 17 项真实业务实跑

- 本次真实受测提交：`b5ae210c40c24df9c85a461d50d9ed21e941eb3e`（基于 #93、含已合并 #151 的 L03 源码，生产注册仍独立）。[GitHub Actions #39277287794](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/39277287794)：**17 passed /0 failed /0 skipped /0 errors**；从 122 份追踪源文件逐字节核对、测试运行前后再核对完整后端和本 eval 范围。
- [原始 gzip](evidence/2026-10-19/20261019T152252495297Z-python3.12.15-public-l01-phase1-b5ae210c40c2.json.gz) 压缩 SHA256 `cc6153930d9ab1ef3adc6a4f8abc9f2570fed8fde82a00b08f92d768da445531`；解压 JSON SHA256 `2b8bb7afb7b3fead67b7d0bba244f132fe45d8470788e30472cd7ca4d554fa96`。运行 UTC 15:22:46—15:22:52。历史旧源码的报告均原样保留。
- 这17条只覆盖已注册 L01 的公共业务/失败/权限/恢复阶段，不等于 96 条设计全部通过。manifest 正确记明 L03 源码已合并但默认运行时注册、安全批准与前端联调未做；其余7个 Blocked 依赖未计入通过或 skipped。


## 票06 运行说明：L01 注册链路的 17 条独立业务评测（继承 #93）

- 本分支依赖评测 PR #93：新增 [17条虚构银行公共业务场景](public-business-cases.md)、[机器清单](public-business-cases.json)、可执行 [测试](test_public_business_eval.py) 与 [固定源码证据工具](run_business_evidence.py)。不把这17条算作96条全部业务设计通过。
- 历史已有 17/17 场景实跑报告（固定老源码），作为历史追溯保留。当前版本的新 CI 和新 gzip 必须在最新评测父提交上单独实跑后再标通过。真实模型、完整 L02/L03、React 和安全专业验收不在这17项覆盖内。


## 2026-10-19 23:04：L03 合入后最新主线独立实跑与原始报告

- 受测提交（对应最新含 PR #151 主线）：`49ce93a0353dcac5923e329d240eff7c7963373f`，父提交 `40a61c32e64c34f4b3872576f05a3d7fc3ee8cc7`。
- [GitHub Actions #39274554945](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/39274554945) 全仓源码检出，Python 3.12.15 / pytest 9.1.1，实际执行 `python evals/bills/run_evidence.py --revision 49ce93a0353dcac5923e329d240eff7c7963373f`。
- **147 passed / 0 failed / 0 skipped / 0 errors**；130 算术 + 17 工具，14/14 固定 Git 源码校验。
- [原始 gzip](evidence/2026-10-19/20261019T150402083715Z-python3.12.15-private-arithmetic-49ce93a0353d.json.gz)，gzip SHA256 `81b6c86671711bed31c4e9e58ca03874bd631a2580879b399dc191dd34034245`；解压 JSON SHA256 `fb67e684e7513f24b57c37e513c9c819fbd74b3fb16c5ffa9608b74488a72914`。
- 时间：UTC 2026-10-19T15:03:59.813010 → 15:04:02.079143。测试模式仅证明14个固定源文件，不证明整仓或完整 BF01–BF07 联合验收。

- [本次原始运行日志](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/39274554945) 的编号 Base64 块已完整还原并交 GitHub 保存为二进制 Git Blob `4bc002edb0dbeeabd8e17fe268d4a5bd0e3abed7`，未手写测试样本。此次独立运行所在主线已含 #151 L03 模块，解决之前 `manifest.py` 被新主线修改造成的来源漂移。
- 旧 gz 以及 PR #93 前面的所有时间、测试计数和SHA 保持原值；多次跑的是同一个测试集合，**不能累计为新的业务场景数量**。

## 2026-10-19 22:11 · 当前新源码正式运行并原字节归档

- **测试提交（源代码，报告提交前）**：`999c1c062cc946f89bae6607eafe6234f4f76a40`，以 10-19 最新 main `399a2feb27637bed3818b198e2bb914b5de2966d` 为父版本；仅在 `evals/bills/run_evidence.py` 增强 tier 分类且兼容现有 SimpleNamespace 钩子测试。
- **运行环境/命令**：[GitHub Actions 39266604025](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/39266604025)，Python 3.12.15 / pytest 9.1.1；先 checkout 完整仓库（fetch-depth=0），安装 `backend[dev]`，实际执行 `python evals/bills/run_evidence.py --revision 999c1c062cc946f89bae6607eafe6234f4f76a40`（无 --source-manifest）。
- **固定源码核验范围**：runner `source_verification=git_object_verified_source_files`，声明的14个 SOURCE_PATHS 与固定提交原始 Git Blob 校验均通过。它不检查 Git 全树、整套依赖或工作区 clean；历史的夸大表述已在上一提交收窄。
- **真实执行**：147 collected，147 passed、0 failed、0 skipped、0 errors、0 collection_errors。`tier_counts`: private_arithmetic=130，evidence_tooling=17，修复了旧报告的分层误分类；这不是147个独立业务场景。
- **原始证据**：[20261019T141112115688Z-python3.12.15-private-arithmetic-999c1c062cc9.json.gz](evidence/2026-10-19/20261019T141112115688Z-python3.12.15-private-arithmetic-999c1c062cc9.json.gz)；压缩文件 SHA256 `b00c8b3a961674e54c6b1d658bd54f18bc5579019522e3db66e295db9b766f47`；解压 JSON SHA256 `f18b553f3a7ebdf5b22c3f4946038e9a1603f58ffbfe82a1238ac3e57c572b6d`；Git 二进制 Blob `14ce7eb22eea125c2fdf9fd76e5908c1186380ec`。从 Actions 成功运行的编号日志块逐段拼接，原字节交给 GitHub `create_blob`（base64），未手写/重建逐样本结果。
- **前序失败原样保留**：首次隔离 CI [39266020163](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/39266020163) 为146 passed /1 failed（分类修改未兼容模拟 Item 缺少 path）；修复后再次完整运行得到上述147/147，不隐去失败历史。
- **归档边界**：这份报告对应固定源码提交 `999c1c062cc946f89bae6607eafe6234f4f76a40`；随后的报告/Markdown 归档提交只增证据与说明，不改变 14 个被测 SOURCE_PATHS。归档提交 SHA 可从 GitHub PR Files/Commits 查看；不是声称 gzip 自包含自己的提交 SHA。完整 BF01–BF07、真实模型/React、安全联合验收单列。


负责人：周恩宇（Ethan）。本轮返修没有改变已合入的 #92。

## 证据口径

- 核心21条 + 增量79条 - 同号细化4条 = 96条业务设计，不等于96条业务通过。
- 账单模块97项（65原单测 + 32契约回归）与33个黄金样本 = 130项私有算术测试。
- 证据、编号、换行兼容等工具校验17项单列；合跑总数147，不能把工具校验当新增业务覆盖。
- 根目录 `python -m pytest -q evals/bills/` 当前包含33项黄金样本 + 17项工具校验 = 50项。
- 每次新报告须用 `python evals/bills/run_evidence.py --revision <40位源码提交>` 实际执行后追加；报告保存逐样本开始、结束时间、结果、映射与14份源码指纹。
- CRLF/LF只做换行归一化，其他字符或规则变化会拒绝。
- GitHub当前CI只执行backend与Mock Bank，本目录专项不能拿CI绿灯代替。

## 历史报告（只保留，不作为本轮证据）

[2026-10-11旧版26黄金样本/91项报告](evidence/2026-10-11/2026-10-11-python313-private-arithmetic-91samples.json.gz)保留原始字节。Erwin已指出其版本锚定不足；它不是当前返修代码的验证结果，不回改时间和哈希伪造成新报告。

## 2026-10-19 较早的源码切片实跑记录（历史）

- 受测远端 **源码提交**：`bd3c2620913ebbb1ea194a599ecf10983eb0fb79`（基于 `main=702f08eda57abfd664fd763cf2d33e3c7f513da9`；本次增量只在 `evals/bills/`）。后继证据提交没有变更被测源码，应以14份 Git blob SHA逐项复核。
- **运行命令**：`python evals/bills/run_evidence.py --revision bd3c2620913ebbb1ea194a599ecf10983eb0fb79 --source-manifest <14文件逐项核对清单>`。被测14份文件已对照GitHub Git blob SHA逐项校对，14/14完全一致；这是隔离本地**源码切片**，不是完整克隆项目的 `git_object_verified_source_files` 模式。
- 本地真实运行结果：**147 passed / 0 failed / 0 skipped / 0 collection errors**。分层为 **130项算术（97模块与契约 + 33黄金ARITH）+ 17项证据/编号工具**；96条业务设计不等于96条通过。
- 原始完整版运行器报告：解压 JSON 的 **SHA256=`8672d792872ccddee093b1b3b1a5e905915dac6a1e59d594fc99177fc371d181`**。完整版包含147条逐样本起止时间、阶段结果及14份源码指纹；**[原始 gzip 已归档](evidence/2026-10-19/20261019T060007618888Z-python3.13.5-private-arithmetic-bd3c2620913e.json.gz)**，文件 Git Blob SHA `f5aa47b5e9c846ee04dff00976314c9b3a3d5b60`，解压SHA256如上。
- [已归档源码与测试收据](evidence/2026-10-19/2026-10-19-147passed-source-verified-receipt.json) 已记录对应远端SHA、14份Blob SHA及分层统计；完整原始报告已按字节入库；摘要收据只用于快速查看被测提交及14份源码Blob。
- PM 侧另有基于完整工作区的独立 `147 passed` 试跑记录（参见 [PR #93 最新说明](https://github.com/DrErwin/hackerthon-bank-agent/pull/93#issuecomment-6260156356)），本地源切片与PM试跑是**不同的证据层**，不能混写为同一次。
- GitHub Actions 默认 CI 没有执行 `evals/bills/`。此历史记录中的完整 checkout 复核缺口由下方新一轮实跑补齐，仍由 Erwin 复核后决定合入。

## 本轮返修待追加的远端版本证据（2026-10-19 已补齐）

- 源码提交：`17031a174aed5b586032ed4c455b0c594182ab9e`；基线：`9741053c304a194a4c3d5ab3048f4dbb8be3b0f9`（运行前核对的最新 main）。当次执行工作树含588个受版本管理文件；恢复 Git 对象是执行环境准备工作，runner 只对 SOURCE_PATHS 的14个固定文件做 Git Blob/工作树逐字节校验，不校验其余文件、整树 SHA、HEAD 或 git status --porcelain。不使用文件切片 manifest 或代用包初始化器；此报告不保证整个依赖闭包或历史完整。
- 实际命令：`python evals/bills/run_evidence.py --revision 17031a174aed5b586032ed4c455b0c594182ab9e`，无 `--source-manifest`。Python **3.12.14**，仓库固定 pytest **9.1.1**。
- 开始：`2026-10-19T07:56:07.088480+00:00`；结束：`2026-10-19T07:56:07.857506+00:00`（北京时间15:56:07）。实际结果：**147 passed / 0 failed / 0 skipped / 0 errors / 0 collection errors**。
- 原始新报告：[20261019T075607860590Z-python3.12.14-private-arithmetic-17031a174aed.json.gz](evidence/2026-10-19/20261019T075607860590Z-python3.12.14-private-arithmetic-17031a174aed.json.gz)。解压 JSON **SHA256=`dfd6416bbafcee6f8fd17070ccdc6b42b2d79b5d64b2c837fd14e4b035e6bf33`**。报告模式 **`git_object_verified_source_files`**；14/14 被测文件与提交的 Git 对象一致，真实包初始化器存在。
- 分层：**96条设计 / 33个黄金样本 / 130项算术（97模块与契约+33黄金）/ 17项工具 / 147项合跑**。运行器当前 `tier_counts` 仍把147项合记为 `private_arithmetic`，这是 PM 已登记的非阻塞分类缺陷；此处按实际测试文件单列130+17，未修改原始报告。
- 另行实际运行 `python -m pytest -q evals/bills/`：**50 passed in 0.23s**。此50项与147项中的黄金/工具测试重叠，不相加为197项覆盖。
- 后继提交只增加新报告并更新README、gaps和本台账；14份被测源码保持相同。历史gzip保留原字节。本轮 14 份源码比对仅证明指定文件来源，不提供整树完整性、干净工作区或依赖闭包校验，也不将局部算术报告扩写为真实模型、HTTP、页面或全部业务验收。

## 2026-10-19 16:29：#153 合入后的最新主线复跑

- 最新主线：`cd7c91ad80652852bb10fef139c2442d756ef359`，已正式合入上游审计引用修复 [PR #153](https://github.com/DrErwin/hackerthon-bank-agent/pull/153)。新受测源码提交：`84b6594e0f989844f62e4c4eaad470e6f1124124`，其父提交就是该 main；工作树当时有589个受版本管理文件，runner只比对14份固定源文件，未对其余新增主线对象做全树校验。
- 实际命令：`python evals/bills/run_evidence.py --revision 84b6594e0f989844f62e4c4eaad470e6f1124124`，无来源切片参数。Python 3.12.14 / pytest 9.1.1。
- 开始 `2026-10-19T08:29:03.945901+00:00`，结束 `2026-10-19T08:29:04.816832+00:00`；**147 passed / 0 failed / 0 skipped / 0 errors / 0 collection errors**，147条唯一逐样本结果。14/14 Git 源码指纹一致，`source_verification=git_object_verified_source_files`。
- [原始 gzip](evidence/2026-10-19/20261019T082904821548Z-python3.12.14-private-arithmetic-84b6594e0f98.json.gz)，解压 JSON SHA256 **`e313bdc1de75a5b70b4c10af0bd21138b8131a65aba5c73ac3668f7491e07371`**。另跑 `python -m pytest -q evals/bills/`：**50 passed in 0.19s**。
- 分层和已披露的 `tier_counts` 分类限制不变：130算术（97模块+33黄金）+17工具=147；50专项与其重叠。不同运行次数不增加设计或业务覆盖数量。
- 归档提交只新增本报告并更新3份文档；旧4份证据文件原字节保留，14份被测源码未改。前序15:56工作树实跑与较早切片各自保留原时间、版本、hash和验证边界。

## 2026-10-19 审查口径更正（核验边界；非新增测试）

依据 [Erwin 的 PR #93 最新审查](https://github.com/DrErwin/hackerthon-bank-agent/pull/93#issuecomment-6267314630)，本轮选择把验证措辞收窄，而不是虚称整仓完整校验：git_object_verified_source_files 仅核实 **14 份指定源文件**的 Git Blob 和工作树字节一致，且 pytest 在该工作树执行；没有检查全部 Git 对象、完整依赖闭包、HEAD 对齐或 git status clean。

历史测试的时间、报告和 hash 保留原字节，不以旧版本报告冒充最新 HEAD 的新一轮实跑。审查仍要求在最新 HEAD 真正执行 run_evidence.py --revision HEAD完整SHA，并归档该提交的 gzip、解压 SHA256 和各层统计；在报告上传之前此项保持未完成。

## 始终未被本算术报告证明的范围

L01/L02/L03真实公开流程、可信身份/B08访问控制、原任务恢复、报告与敏感导出、真实模型、HTTP/React及专业安全审查仍分别验收。平台真实工厂替换桩由Erwin按Issue #123负责；账单功能本身归周恩宇，不能互相顶替完成声明。
