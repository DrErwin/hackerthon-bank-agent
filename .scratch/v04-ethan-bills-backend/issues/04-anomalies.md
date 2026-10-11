# 04：L02交易定位与四类异常规则

Ticket ID: v04-ethan-bills-backend/04
Type: 开发
Owner: 周恩宇
Directory: backend/app/modules/bills/
Status: blocked
Package: [v04-bills/01](../../v04-bills/packages/01-bills-backend.md)
Spec: [本人规格](../spec.md)
Core scenarios: [BF02/BF05/BF06](../../v04-bills/spec.md)
Blocked by: [03公开读取与原任务路径](03-public-summary.md)；Issue91的对应公共模型
Verification: locate候选不代选；single核对银行事实；scan仅规则4；OR条件分开、基线不足、亲属例外、夜间端点、月末/锚点/日期容差；不代冻结/取消。

## 验收

只按PRD与§5.3/§5.9，RuleCheck区分evaluated与insufficient_data；不把attention当安全执行器risk。06:00恰好端点先由Erwin明确，不能猜答案后写通过。
