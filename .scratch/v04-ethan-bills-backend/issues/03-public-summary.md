# 03：L01公开统计/明细与原任务接入

Ticket ID: v04-ethan-bills-backend/03
Type: 开发
Owner: 周恩宇
Directory: backend/app/modules/bills/
Status: blocked
Package: [v04-bills/01](../../v04-bills/packages/01-bills-backend.md)
Spec: [本人规格](../spec.md)
Core scenarios: [BF01/BF05/BF06](../../v04-bills/spec.md)
Blocked by: [01统计内核](01-statistics-core.md)合入；[Issue #91](https://github.com/DrErwin/hackerthon-bank-agent/issues/91)的公共类型/B08公开实现与合入证据（Erwin）
Verification: 注册L01；本人登录读取、跨用户拒绝、全部账户完整取数、自然语言澄清/修改/原任务恢复；HTTP/模型证据与纯算术分开。

## 验收

- 引用app.contracts公共模型，统一安全执行入口调用B08；无私有银行读取。
- 不自行猜账户/月份，失败不报0；summary/details输出按§5.3。
- 真实接口形态可调用且测试后向frontend-complete/01发出接入信号；仅文档定义不算信号。
