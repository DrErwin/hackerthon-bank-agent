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
Verification: 稳定ID去重、八字段、逐规则映射；手算golden数据与26个局部样本；报告按指南§六压缩归档。真实业务保持Blocked。

## 交付与验收

- 保留核心21条；新编号不伪造额外覆盖，同号细化不重复统计。
- 覆盖正常/反例/边界/修改/失败恢复/交叉；未明规则和缺数据显式列出。
- 提供虚构流水fixtures和算术层自动化；不把验证自己手写期望等同于真实Agent评测。
- 数据/代码只在evals/bills；与01按两层Draft依赖交付，不合并他目录改动。
- 文档数量、已自动化、局部运行与真实业务结果分别记录；全部业务未过不标完成。

## Comments

- 2026-10-11：覆盖设计与26个私有算术样本已准备；与01的65项模块测试合跑91项通过。仅本次局部组合，不是主线或公共链路验收。
