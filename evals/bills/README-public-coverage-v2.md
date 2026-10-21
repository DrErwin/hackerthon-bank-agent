# 票06：L02/L03 真实公共业务评测 + 四类异常各三对照（第二阶段候选）

> 状态：**已实现并提交测试代码，未取得当前组合的专项执行结果，不能记 Passed。**
> Owner: Ethan / `zhouey314-cloud`; Ticket: `v04-ethan-bills-backend/06`. 目录仅 `evals/bills/`。

## 本轮新增测试

- 原一期 L01：17个已实跑并合入的**独立**公共业务场景（[PR #198](https://github.com/DrErwin/hackerthon-bank-agent/pull/198)）；不是 96 条旧设计全部实跑。
- 新一期：L02 公开入口14场景、L03公开入口14场景、异常规则1—4各3种新银行流水对照（12个），合计**40个不重复参数用例**。所有用例经真实注册的 BillsEntry + Harness + task-scoped SecurityGate/执行器 + BankGateway + 新建SQLite MockBank；规则对照用测试专属 `MockBankStore.seed_ledger_rows` 新增真实可读取的行，插入后才计算银行完整表 SHA256，不修改生产 seed 文件。
- 分类覆盖：L02候选定位/选中后重读/周期扣款扫描/缺月/选账户/含糊金额/空候选/半月/取消/幂等/权限拒绝/跨会话恢复；L03月度/年度部分范围、报告/选择账户、比较和未来期间澄清、类别筛选、权限拒绝、幂等、B08失败重试、打印/分享无隐式权限。
- 异常：规则1金额突变（命中/不命中/可信亲属缺失），规则2陌生收款方（命中/既有收款方/缺对手方ID），规则3夜间（夜间命中/白天/非支出夜间不适用），规则4周期扣款（三月匹配/不匹配/缺商户ID）。**规则3第三条是 noneligible，不谎称 insufficient。**

## 如何执行与验收

在仓库根目录、完整git checkout、已安装 `backend[dev]` 依赖后：

```bash
python -m pytest -q evals/bills/test_public_coverage_v2.py
python evals/bills/run_public_coverage_v2.py --revision "$(git rev-parse HEAD)"
```

runner 先校验全部Git源码，然后独立收集**恰好40**个参数用例；拒绝跳过/缺测试/失败/缺只读银行SHA/任何资金写入；再次校验源码，记录精确SHA、样本、来源与完整脱敏JSON.gz到 `evals/bills/evidence/YYYY-MM-DD/`，结果为 Passed/Failed 而非宣传式成功。Windows CRLF 使用既有一致化检验。运行产生的原始报告要单独提交归档并核对压缩和解压 SHA256。

**特别说明：GitHub 默认 Repository checks 只执行 backend 和 mockbank，既不运行新40例，也不运行独立 runner。默认CI绿不等于40例通过。必须使用可执行环境专项实跑并归档。**

## 尚未核销

- 新40例是否运行成功：**待专项实跑**（提交测试 ≠ 通过）。
- 所有异常/错误种类的完整公共 API HTTP覆盖、SSE/浏览器/GLM+生产安全，继续独立对应票07、Erwin和Ringo。
- 个人整票及v0.4 BF01—BF07联合验收：**仍为 partial / in_progress**。测试替身是 scripted planner/LOW风险与授权事实，不代真实模型与专业安全审查。
