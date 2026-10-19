# 账单评测运行台账

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
