# 01：L01 私有统计内核与局部测试

Ticket ID: v04-ethan-bills-backend/01
Type: 开发
Owner: 周恩宇（Ethan）
Directory: backend/app/modules/bills/
Status: in_progress
Package: [v04-bills/packages/01-bills-backend：账单业务能力与评测](../../v04-bills/packages/01-bills-backend.md)
Spec: [本人实施规格](../spec.md)
Core scenarios: [BF01/BF03 的算术子路径](../../v04-bills/spec.md)
Blocked by: None（私有计算可独立验证；公开注册/真实取数另由03依赖Issue91）
Verification: 运行本目录test_statistics.py；核对金额与来源范围、无网络/银行写操作；不宣称BF全路径通过。

## 交付与验收

- 确定性计算消费/退款/净额、转入转出、七类、对比、月均与明细过滤。
- 金额不经float或字符串隐式转换；零/负净额、截至时间和半开区间有断言。
- 内部数据对象不复制公共wire模型；不直读银行私有实现；不注册假公开能力。
- manifest与README如实标注当前仅内核、无工具/副作用。
- 单目录PR，待Erwin审查，不自行合并。局部通过不是整包accepted。

## Comments

- 2026-10-11：按用户明确实施并提交要求启动；私有内核本地65项测试通过，尚待PR及审查。
