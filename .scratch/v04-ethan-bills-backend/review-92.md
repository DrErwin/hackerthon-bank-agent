## 双轴只读审查结论（Erwin，2026-10-12）：**请先修 3 处阻塞项再合**

基线 `git diff main...origin/feat/bills/statistics-core`（merge-base `3aff976`，已含 `c371cf0`/PR #97）；4 文件、+543/−4，全在 `backend/app/modules/bills/`；我在隔离工作区独立复跑 `app/modules/bills/` = **65 passed**，与你的声明一致 ✓。

### 必须修（合入门槛）

1. **复制冻结七类码，未引用公共契约**（硬）：`_statistics.py:16-17` 用字符串字面量重声明七类，而 `app.contracts.common.Category`（`common.py:84-93`）已存在且本目录可 import（`manifest.py:2` 已证明）。根 `AGENTS.md`「提交前自查·引用公共契约，不复制一份」。
   → 改为 `from app.contracts.common import Category`，字面量从枚举派生（如 `tuple(c.value for c in Category)`）。
2. **退款类别未按 §5.9 继承原消费**（硬·部分）：`LedgerRow` 丢掉 `original_transaction_id`/`original_occurred_at`，`totals()`（`:181,187`）直接采信退款行自身的商户类别；公共契约 §5.9（`docs/contracts/公共契约-2026-09-23.md:401` 一带）与 02 PRD 第 84 行要求**按交易性质识别、类别继承原消费**，不是靠退款行的商户类别。现有种子恰好两边都是 dining（`a1-m1-refund` ← `a1-m2-canteen`），属**潜在错账**。
   → 把两个原单字段带进内部投影，退款按原消费类别归类；`test_statistics.py:62` 那个名为 `..._category_inherited` 的用例目前只喂了同类别退款，请改成**原消费与退款类别不同**的样本（否则名字掩盖缺口）。
3. **文档与 PR 正文与事实不符**（硬·文档失真）：`README.md:15` 与本 PR 正文仍称「公共 Transaction / 账单模型缺失」；实际 `contracts/bills.py`、`bank.py` 的 `Transaction` 已随 #97 合入 main，且是本分支 merge-base 的祖先（**只剩 B08 查询缺**）。ticket 01:19 要求如实标注。
   → 更新 README 与正文措辞（「契约已就绪、缺 B08 取数」），并顺手补上场景编号（BF01—BF07）与「是否触及契约」声明。

### 建议修或登记（不阻塞合入，但不能沉默）

4. `select_rows`（`:207-212`）按 `nature` 覆盖类别标签（transfer→transfer、interest→other），而契约按 `category` 过滤、并要求返回行内类别一致（`contracts/bills.py:141-142`，`contracts/test_bills_contracts.py:245-247` 明确接受 `nature=transfer` + `category=transport` 的行）。种子恰好 `nature==category` 所以看不出来 → 要么改为按 category 过滤，要么在 `evals/bills/gaps.md` 登记这一取舍。
5. `valid_shares`（`:190-194`）在任一类别净额为负时把**七类 share 全置 None**，严于契约（`contracts/bills.py:87-88` 只否负净额那一类与 transfer）→ 登记 gaps，或按契约放宽。
6. 类别映射口径在 `totals()` 与 `select_rows()` 写了两份，容易漂移 → 收口到一处。
7. `manifest.py:9` 的 `MANIFEST` 全仓无消费方（`transfer/__init__.py:3` 是同目录既有约定）；空能力清单是 ticket 01 要求的，请说明用途或对齐既有导出方式。

### 已核通过（无需改）

整数分与 `Fraction`、半开区间、跨月退款不回溯、先乘后除且四舍五入（§5.9）、`as_of = min(source_as_of)`、失败不降级为空批次、行/类别排序确定、私有对象未注册成第二套契约、未越界改 contracts/storage/bank/security ✓

修完 push 到本分支即可（我会 sync 后再跑一次独立复验 + 合并）。#93 依赖本 PR，先合这个。
