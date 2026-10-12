## 双轴只读审查结论（Erwin，2026-10-12）：**证据链请先修 3 处再合**

审查范围＝本 PR 自己的增量：`git diff origin/feat/bills/statistics-core...origin/test/bills/arithmetic-coverage`（1 提交 `a81de96`、8 文件，全在 `evals/bills/`，未夹带其他目录 ✓）。我在隔离工作区独立复跑：`app/modules/bills/`（#92 内容）65 passed、`evals/bills/` **26 passed**（注意要先把 `backend/` 放进 `PYTHONPATH`，见下第 4 条）✓；`run-log.md` 的 sha256 与 gz 内 `code_sha256` 也已核对一致 ✓。方向是对的，问题集中在**证据能不能被钉住和复现**。

### 必须修（合入门槛）

1. **运行版本没有钉住**（证据可复现性）：`run-log.md:8` 称「每条实际结果与时间保存在报告内」，实际报告里只有单个 `recorded_at` ＋ per-test `seconds`；唯一版本标记是 `source_repository_baseline=65d1a70`（该提交既没有 `_statistics.py` 也没有本评测文件），`uploaded_revision=null` → **这次 26/91 的通过结果无法从提交复现**。
   → 把被测代码版本钉到本次运行的 `a81de96`（或说明取 `source_repository_baseline` 的原因并保证该基线可复现），并把「每条结果与时间」落实到每个样本一条记录，或改写 run-log 的措辞与实际一致。
2. **`gaps.md:13` 出处记错**：它把 share_bps 取整与「占比不要求相加 10000」登记为「契约未明」，但契约 §6.11（`docs/contracts/公共契约-2026-09-23.md:592`）已经写明「share_bps 和 change_bps 仅为展示比例，最后四舍五入……占比因取整不要求相加精确等于 10000」。
   → 更正出处，并把该口径补成用例（fixture 目前没有 `share/bps/rank` 字段，`test_statistics_eval.py:38,43` 只比精确 Fraction 与整体 null），或明确登记为未测。
3. **评测样本与设计用例没有互指**：`ARITH-` 前缀在 `README.md`/`coverage-matrix.md`/`expanded-cases.md` 中出现 0 次，`expanded-cases.md:15-89` 的「自动化映射」仍写待运行，违反 `evals/README.md:50`、`:120` 的「契约 ↔ 验收例 ↔ 评测用例」链。
   → 在矩阵与 expanded-cases 里标出每个 ARITH 样本对应的用例编号与状态。

### 建议修（不阻塞，但影响可用性）

4. **套件按指南跑不起来**：`evals/README.md:159` 要求 `pytest evals/bills/` 全绿，但 `test_statistics_eval.py:6` 直接 import 私有内核，而 `evals/bills/` 没有 `conftest.py`（对照 `evals/transfer/conftest.py:6-8`）；CI 也只跑 backend 与 `evals/mockbank`。我是手工设 `PYTHONPATH=<repo>/backend` 才跑通的。
   → 加一个 `evals/bills/conftest.py`（把 `backend/` 加入 `sys.path`）让指南命令直接可用；是否把该目录接进 CI 可另议。
5. PR 正文补「场景编号（BF01—BF07）」与「是否触及契约」声明（`AGENTS.md` 提交前自查）；提交前缀 `test`、Draft＋Depends on PR #92 已合规 ✓。
6. 小项：`test_statistics_eval.py:12-21,29,41` 的 `dict.get` 兜底 + `(snapshot, now)` 元组返回（Data Clumps/Primitive Obsession），`coverage-matrix.md:3` 的「前缀约定」建议直接写全。

### 已核通过

增量＝票面范围、矩阵无悬空编号（92 = 21 + 75 − 4 与 `README.md:15` 自洽）、证据文件主动否认银行/HTTP/模型/页面结论、未把部分覆盖当全量、核心口径（退款净额、转账单列、利息不入消费、非正基期 change=null、月均 ×30÷天数、`as_of` 取最早）已钉 ✓

修完 push 到本分支；**合入顺序：#92 先合**（本 PR 含 #92 的提交，届时我按仓库约定帮你把本 PR 只保留自己的改动再以最新 main 为目标）。
