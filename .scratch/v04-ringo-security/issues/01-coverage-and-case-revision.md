# v04-ringo-security/01：覆盖缺口及冲突用例修订

Ticket ID: v04-ringo-security/01
Package: [v04-security/01：检测器与评测完整性](../../v04-security/packages/01-detector-and-coverage.md)
Spec: [本人工作规格](../spec.md)
Core scenarios: RS09；保持 RS02、RS04、RS06、RS07 的既定判据
Type: 评测
Owner: Ringo
Directory: evals/security/
Status: resolved（#159 合入；2026-10-21 #211 覆盖审计与数量门收尾；验收条目例外按 PM 决定 A 登记，见 evals/security/coverage-audit-2026-10-21.md）
Blocked by: None
Source issue: #88（[#86](https://github.com/DrErwin/hackerthon-bank-agent/issues/86)、[#88](https://github.com/DrErwin/hackerthon-bank-agent/issues/88)）
Verification: 核对 JSONL 全部主编号唯一、参数展开及轮次统计；检查覆盖引用与结果模板一一对应，复核 R06 和八组下限及异常类型。运行本目录已有结构/目录测试；仅文档变化做内容与链接检查，涉及数据及测试代码按相应验证和独立 PR 处理。

## 交付结果

补齐适用规则及八个低于下限的分组，核定 R06 的真实管理分支；修订 SEC-E-006/v06 的撤销前置，更新完整数据关系。

## 验收条件

- [x] 先按规格核对逐功能覆盖；八组差额为 15 个主用例，M 组新增两例关联 R06，实际条数由独立规则决定。
- [ ] 各功能至少 10 条、各类异常至少 3 条分别核查；变体和同义改写不计为新增主用例。
- [x] 已发布用例 ID 保持稳定；v06 保留历史排除追踪，使用符合撤销语义的前置及重复/冲突判据。
- [x] 正文、JSONL、覆盖 CSV、结果模板及 README 规模保持一致；重算主用例、参数实例和计划轮次。
- [x] 规则有来源；缺少自动化映射或运行证据的用例如实保持待实现、待运行或 Blocked。
- [x] MAT 范围已由 #133 确定，相关新增由票 05 单独交付；原报告及历史核查保持原样。

## 实施边界

本票只修改 Directory 指定目录。开发或编写运行代码时使用 implement；有代码时按 code-review 分别核对仓库规范与本票要求，实际测试和本人批准分别记录。纯文档按仓库例外做内容检查；代码和执行配置走独立 PR 及必要验证。

本票在 2026-10-15 随已确认的七项拆分建立。历史建立时尚未实施，当前结果以本票Comments及关联PR为准。

## Comments

- 2026-10-15：Ringo 本人在本会话确认测试边界及七项拆票。接票执行前补实际领取时间与状态；本条不作为已执行或验收通过的记录。

- 2026-10-19：[Issue #88 最新 PM 排期结论](https://github.com/DrErwin/hackerthon-bank-agent/issues/88)撤回 10-18 的延期决定，本票保留在 v0.4。分母随实际用例变更重算，旧批次及其 Blocked 状态保持；本条仅更新排期与依赖。

- 2026-10-19 实施记录：[PR #159](https://github.com/DrErwin/hackerthon-bank-agent/pull/159)已提交且CI成功，137/289/345，新增15个独立主用例，56项回归通过；全量20 Passed / 0 Failed / 325 Blocked。R06关联10条，12组均达到10条，四类异常均至少3条。B18局部探针通过，原预约及模型路由仍缺证据，整例Blocked。逐功能完整行为覆盖未据数量推定。后续MAT增量单独见票05及PR #163，历史批次保持。
