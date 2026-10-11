# 06：完整账单业务自动化与证据

Ticket ID: v04-ethan-bills-backend/06
Type: 评测
Owner: 周恩宇
Directory: evals/bills/
Status: blocked
Package: [v04-bills/01](../../v04-bills/packages/01-bills-backend.md)
Spec: [本人规格](../spec.md)
Core scenarios: [BF01—BF06](../../v04-bills/spec.md)
Blocked by: [02覆盖与数据](02-coverage-and-fixtures.md)、[03](03-public-summary.md)/[04](04-anomalies.md)/[05](05-report-export.md)各对应路径；逐路径就绪即验证，不等全写完
Verification: 冻结规则逐项映射；每功能>=10、每类异常>=3并消除缺口；Passed/Failed/Blocked分别报告，原始JSON.gz/sha256归档。

## 验收

测试调用真实公开业务能力与银行接缝，不只调用私有计算器；不以stub/skip/xfailed制造全绿。专业检测与业务响应分层记录，不代Ringo签核。
