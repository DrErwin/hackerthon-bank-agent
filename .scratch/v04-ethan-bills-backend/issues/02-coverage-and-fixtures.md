# 02：账单覆盖规划、数据与算术黄金样本

Ticket ID: v04-ethan-bills-backend/02
Type: 评测
Owner: 周恩宇（Ethan）
Directory: evals/bills/
Status: in_progress
Package: [v04-bills/packages/01-bills-backend：账单业务能力与评测](../../v04-bills/packages/01-bills-backend.md)
Spec: [本人实施规格](../spec.md)
Core scenarios: [BF01—BF06覆盖设计；当前仅算术子断言可运行](../../v04-bills/spec.md)
Blocked by: None（文档/数据）；自动化算术样本依赖 [01](01-statistics-core.md)
Verification: 稳定ID去重、八字段、逐规则映射；手算golden数据与33个局部样本；报告按指南§六压缩归档。真实业务在 [06](06-full-business-eval.md) 逐路径记录，本票算术结果不代替业务验收。

## 交付与验收

- 保留核心21条；新编号不伪造额外覆盖，同号细化不重复统计。
- 覆盖正常/反例/边界/修改/失败恢复/交叉；未明规则和缺数据显式列出。
- 提供虚构流水fixtures和算术层自动化；不把验证自己手写期望等同于真实Agent评测。
- 数据/代码只在evals/bills；与01按两层Draft依赖交付，不合并他目录改动。
- 文档数量、已自动化、局部运行与真实业务结果分别记录；全部业务未过不标完成。

## Comments

- 2026-10-11：覆盖设计与26个私有算术样本已准备；与01的65项模块测试合跑91项通过。仅本次局部组合，不是主线或公共链路验收。

### 2026-10-19 15:56：完整源码运行与证据归档（前序基线历史）

- [PR #93](https://github.com/DrErwin/hackerthon-bank-agent/pull/93) 受测源码 `17031a174aed5b586032ed4c455b0c594182ab9e`，基线 `9741053c304a194a4c3d5ab3048f4dbb8be3b0f9`；最终证据 head `eef9b8e998f0adab716e30d7276f264d9181119f`。源码工作区完整，含 588 个受版本管理文件；14 份被测源码与 Git 对象一致。
- 在仓库根目录实际运行 `python evals/bills/run_evidence.py --revision 17031a174aed5b586032ed4c455b0c594182ab9e`，不使用 `--source-manifest`。Python 3.12.14 / pytest 9.1.1；开始 `2026-10-19T07:56:07.088480+00:00`，结束 `2026-10-19T07:56:07.857506+00:00`；**147 passed / 0 failed / 0 skipped / 0 errors / 0 collection errors**。
- 新报告 `evals/bills/evidence/2026-10-19/20261019T075607860590Z-python3.12.14-private-arithmetic-17031a174aed.json.gz`；解压 SHA256 `dfd6416bbafcee6f8fd17070ccdc6b42b2d79b5d64b2c837fd14e4b035e6bf33`；模式 `git_object_verified_source_files`，包含 147 条逐样本结果与 14 份源码指纹。旧证据保留原始字节，没有覆盖或回填历史时间。
- 统一计数：21 条核心 + 79 条增量 − 4 条同号细化 = **96 条设计**；97 项模块与契约 + 33 项 ARITH 黄金 = **130 项算术**；工具校验 **17 项**，合跑 **147 项**。`tier_counts` 的 147 项合记问题为 PM 已登记的非阻塞分类缺陷，说明文档按 130 + 17 单列，原报告不改写。
- 另行 `python -m pytest -q evals/bills/` 为 **50 passed in 0.23s**，与 147 项中的黄金和工具部分重叠。[CI 39219881038](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/39219881038) 已 success，后端 **698 passed**、Mock Bank **14 passed**；根执行者另做本地后端 **698 passed**。默认 CI 不执行此目录专项，不能用 CI 代替上述 147 项证据。
- 独立 Spec 复核确认新报告、14 份指纹、原始 gzip 与历史文件保留符合本轮证据要求。保持 `in_progress`，待 Erwin 决定合入；没有把算术证据声明为全部业务、真实模型、HTTP、页面或专业安全验收。

### 2026-10-19 16:29：#153 合入后基于新主线再次实跑

- 新受测源码 `84b6594e0f989844f62e4c4eaad470e6f1124124` 的父提交为最新 main `cd7c91ad80652852bb10fef139c2442d756ef359`；完整树 589 个受版本管理文件。归档增量本地提交 `cac529389e25f5eacfed3bc3f32dbe1786cfb67c` 只新增本轮 gzip 并更新 README、gaps、run-log，最终远端与新 CI 结果见本节发布记录。
- 实际命令 `python evals/bills/run_evidence.py --revision 84b6594e0f989844f62e4c4eaad470e6f1124124`；Python 3.12.14 / pytest 9.1.1。开始 `2026-10-19T08:29:03.945901+00:00`，结束 `2026-10-19T08:29:04.816832+00:00`；**147 passed / 0 failed / 0 skipped / 0 errors / 0 collection errors**，不使用来源切片参数。
- 新报告 `evals/bills/evidence/2026-10-19/20261019T082904821548Z-python3.12.14-private-arithmetic-84b6594e0f98.json.gz`；解压 SHA256 **`e313bdc1de75a5b70b4c10af0bd21138b8131a65aba5c73ac3668f7491e07371`**。独立专项 `python -m pytest -q evals/bills/` 为 **50 passed in 0.19s**。
- 独立 Spec 复核直接比对压缩原字节、解压 SHA256、14 份 Git blob / 规范化 SHA256 / 工作区字节及哈希：全部一致。147 条唯一逐样本记录均 passed，起止时间和阶段结果有效；此前 4 份证据逐字节保留。受测提交确实基于 cd7c91ad，未把前一轮运行改标成新主线证据。
- 96 / 33 / 130 / 17 / 147 口径不变，50 项仍与 147 项重叠；两次实际复跑也不相加为新覆盖。已披露的 `tier_counts` 非阻塞分类限制保留；前序 CI 698/14 不自动视为本版本 CI 结果。
- 最终远端 [d367456961679d5431d4f1f534f723c9b6b079d9](https://github.com/DrErwin/hackerthon-bank-agent/commit/d367456961679d5431d4f1f534f723c9b6b079d9) 已推送，与归档 cac529389e25f5eacfed3bc3f32dbe1786cfb67c 的 Git 树均为 `e2ef7b203df170f4dde5704cbd1e001817f9dc3c`；[CI 39223750787 / job 117964933338](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/39223750787/job/117964933338) 已 success，根执行者核对为后端 **699 passed**、Mock Bank **14 passed**。
