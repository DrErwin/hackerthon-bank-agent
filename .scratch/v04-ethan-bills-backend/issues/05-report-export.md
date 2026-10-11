# 05：L03受控报告与导出接线

Ticket ID: v04-ethan-bills-backend/05
Type: 开发
Owner: 周恩宇
Directory: backend/app/modules/bills/
Status: blocked
Package: [v04-bills/01](../../v04-bills/packages/01-bills-backend.md)
Spec: [本人规格](../spec.md)
Core scenarios: [BF03/BF04/BF06](../../v04-bills/spec.md)
Blocked by: [03公开统计](03-public-summary.md)；公共受控报告/下载/本次明细验证接口可用（实施时核对，缺口另登记给对应owner）
Verification: 三块卡片、月均/范围完整性、分享不增权；卡片普通导出、明细验证成功/失败/过期/越权；资源生成和恢复有真实证据。

## 验收

不夹带趋势/异常块，不生成无权下载；不自行复制验证码/资源权限系统。局部报告数据生成与真实可下载资源分开记录。
