# v04-ringo-security/09：业务声明与安全预期独立冻结

Ticket ID: v04-ringo-security/09
Package: [安全工作线](../../v04-security/packages/01-detector-and-coverage.md)
Spec: [本人工作规格](../spec.md)
Type: 安全返修
Owner: Ringo
Directory: backend/app/security/
Status: in_review（实现与定向回归已提交，完整CI已通过，真人批准分别记录）
Blocked by: [PR #149](https://github.com/DrErwin/hackerthon-bank-agent/pull/149)先合入，再重基main
Source issue: [Issue #164](https://github.com/DrErwin/hackerthon-bank-agent/issues/164)
Verification: 原声明合法对照、每字段及嵌套权限漂移拒绝；真实Gate与执行器的降权请求在处理器调用前停止。独立AI复核、完整后端及真人批准分别记录。

## 结果与边界

补审PR #150发现白名单直接持有业务模块可变声明，原地降权后自比全等，真实门可跳过确认验证并调用模拟处理器。转账同类声明也存在同一问题，Ringo按安全目录归属同步固定原值；业务授权取舍变化0。

[Draft PR #165](https://github.com/DrErwin/hackerthon-bank-agent/pull/165)依赖#149，只审订阅及转账十二条独立预期的增量；与#149账单三条组合后，当前十五条声明均与业务对象分离。策略v04-frozen-tool-policy-2，原确认与风险处置保持。

- [x] 原六条嵌套列表及真实退订门共7项Red复现；产品缺口与Pydantic测试准备问题分别记录。
- [x] 新增146实例，含12合法、120字段漂移、12嵌套及两个真实门降权拒绝；处理器spy零调用。
- [x] 安全、订阅模块及订阅HTTP定向288 passed，Standards/Spec复核遗留均0。
- [x] 本提交CI完整后端897 passed、模拟银行评测14 passed，见PR #165 checks；前置合入后仍须重基main。
- [ ] 真人专业批准与最终合并另行记录。

本票防配置声明漂移，部署中任意恶意Python代码另属信任边界。真实检测仍待票02和Issue #160。代码限定security目录，未改公共契约或业务模块。

本机全量另出现896 passed / 1 failed的20ms重放断言异常，随即单例及服务目录复跑通过，已交[Issue #166](https://github.com/DrErwin/hackerthon-bank-agent/issues/166)待查；当前CI897/14通过与该异常分别记录，未据单次复跑宣称问题已消失。
