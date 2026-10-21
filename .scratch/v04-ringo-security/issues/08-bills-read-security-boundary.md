# v04-ringo-security/08：账单读取安全边界与声明冻结

Ticket ID: v04-ringo-security/08
Package: [v04-security/01：安全工作线追加范围](../../v04-security/packages/01-detector-and-coverage.md)
Spec: [本人工作规格](../spec.md)
Core scenarios: RS11 至 RS14，见本次追加规格
Verification: 验证本人只读放行、跨用户及旧轮次拒绝、声明变化阻断和银行账户归属；通过真实安全门核对零资金副作用。审计原文泄露整改由账单负责人另票实施，整改前保留缺口。
Type: 开发
Owner: Ringo
Directory: backend/app/security/
Status: in_review（#149 已合入 main；待 Ringo 真人复核）
Blocked by: None（业务口径引用 Issue #137 的 PM 临时决定）
Source issue: [Issue #137](https://github.com/DrErwin/hackerthon-bank-agent/issues/137)

## 交付结果

按 Erwin 已定的本人账户读取口径，补齐安全侧书面意见；将账单白名单固定在安全目录，避免业务声明随部署变化自动扩大权限。本人读取沿用 LOW、免确认和免验证；敏感导出继续使用原验证路径。

## 验收条件

- [x] 仅冻结的 bills.summarize、bills.bank.list_accounts、bills.bank.list_transactions 获准；新增能力保持默认拒绝。
- [x] 六项安全声明及输入、输出和处理器引用变化均被阻断，业务声明修改须新安全评审。
- [x] 合法读取无需转账风险夹具；转账缺事实仍暂停，原高中风险处置保持。
- [x] 真实安全门与银行读取组合验证本人查询、他人账户与不存在账户的等价拒绝，并记录零资金动作。
- [x] 审计规则及已知原文泄露位置书面登记，账单整改交其 owner；AI 检查、真人签核与合并状态分别记录。

## Comments

- 2026-10-19：依据 Ringo 当前的逐项执行授权开始，业务规则采用 [PM 临时结论](https://github.com/DrErwin/hackerthon-bank-agent/issues/137#issuecomment-6250123462)，本票范围为安全目录，公共契约和账单实现保持。
- 2026-10-19：实现、测试和 AI 双轴审查见 [执行记录](../verification-2026-10-19.md)。单目录代码准备提交，真人签核与最终合并保持待办；账单审计整改沿用 Issue #145。

- 2026-10-19 实施记录：[PR #149](https://github.com/DrErwin/hackerthon-bank-agent/pull/149)已重基main ecf90d0并保留订阅策略，head fad93a3 CI成功。最新安全目录100 passed、完整后端751 passed；两轴AI复核遗留0。#137四项书面意见已提交，#145审计原文整改由周恩宇另票实施。实际真人签核仍单独记录。
