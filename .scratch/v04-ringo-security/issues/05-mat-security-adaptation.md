# v04-ringo-security/05：MAT 材料的安全评测接入

Ticket ID: v04-ringo-security/05
Package: [v04-security/01：检测器与评测完整性](../../v04-security/packages/01-detector-and-coverage.md)
Spec: [本人工作规格](../spec.md)
Core scenarios: RS01、RS05、RS09、RS10，以 #133 定稿集合为准
Type: 评测
Owner: Ringo
Directory: evals/security/
Status: blocked
Blocked by: [Issue #133：MAT 改编验收范围对齐](https://github.com/DrErwin/hackerthon-bank-agent/issues/133)（Erwin）；按所选样本关联 /02 与 /03 的实际能力
Source issue: #88 / #133（[#86](https://github.com/DrErwin/hackerthon-bank-agent/issues/86)、[#88](https://github.com/DrErwin/hackerthon-bank-agent/issues/88)）
Verification: 核对来源与编号映射、数据安全及合法对照；先做本票可执行离线验证，实际检测证据来自已接入链路。MAT 用例编写完成与识别通过分别留痕。

## 交付结果

按确认范围把已有公开研究材料改编到银行安全实例，保留来源与合法对照，证明实际安全检测。

## 验收条件

- [ ] 先引用 #133 的明确范围结论，再确定必交集合及可选增量。
- [ ] 逐项记录公开来源、项目原创改编内容与 SEC 编号/参数关系，历史转账侧 MAT 结果单独引用。
- [ ] 每个改编场景提供合法对照和可准备的合成前置，真实识别与夹具响应分别判定。
- [ ] 新增主用例或参数实例后重算分母，旧批次使用原规模；已发布 ID 保持。
- [ ] 付费模型调用执行前另行确认；缺观察或资料入口的样本保持 Blocked。

## 实施边界

本票只修改 Directory 指定目录。开发或编写运行代码时使用 implement；有代码时按 code-review 分别核对仓库规范与本票要求，实际测试和本人批准分别记录。纯文档按仓库例外做内容检查；代码和执行配置走独立 PR 及必要验证。

本票在 2026-10-15 随已确认的七项拆分建立。当前未开始实施，最终交付以本票实际证据为准。

## Comments

- 2026-10-15：Ringo 本人在本会话确认测试边界及七项拆票。接票执行前补实际领取时间与状态；本条不作为已执行或验收通过的记录。
