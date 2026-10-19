# v04-ringo-security/05：MAT 材料的安全评测接入

Ticket ID: v04-ringo-security/05
Package: [v04-security/01：检测器与评测完整性](../../v04-security/packages/01-detector-and-coverage.md)
Spec: [本人工作规格](../spec.md)
Core scenarios: RS01、RS05、RS09、RS10，以 #133 定稿集合为准
Type: 评测
Owner: Ringo
Directory: evals/security/
Status: blocked（五项材料参数化与离线探针已交付，真实检测及间接观察待补）
Blocked by: 按所选样本关联 /02 真实检测能力与 /03 观察端；付费调用另确认预算。#133 范围澄清已完成。
Source issue: #88 / #133（[#86](https://github.com/DrErwin/hackerthon-bank-agent/issues/86)、[#88](https://github.com/DrErwin/hackerthon-bank-agent/issues/88)）
Verification: 核对来源与编号映射、数据安全及合法对照；先做本票可执行离线验证，实际检测证据来自已接入链路。MAT 用例编写完成与识别通过分别留痕。

## 交付结果

按确认范围把已有公开研究材料改编到银行安全实例，保留来源与合法对照，证明实际安全检测。

## 验收条件

- [x] 已引用 #133 的明确结论：现有 MAT-VFY16-01 至 04、MAT-FRAUD-01 的适用项为最小必交集合，额外扩充可选；#88 的 10-19 决定将实施保留在 v0.4。
- [x] 逐项记录公开来源、项目原创改编内容与 SEC 编号/参数关系，历史转账侧 MAT 结果单独引用。
- [x] 每个改编场景提供合法对照和可准备的合成前置，真实识别与夹具响应分别判定。
- [x] 新增主用例或参数实例后重算分母，旧批次使用原规模；已发布 ID 保持。
- [x] 付费模型调用执行前另行确认；缺观察或资料入口的样本保持 Blocked。

## 实施边界

本票只修改 Directory 指定目录。开发或编写运行代码时使用 implement；有代码时按 code-review 分别核对仓库规范与本票要求，实际测试和本人批准分别记录。纯文档按仓库例外做内容检查；代码和执行配置走独立 PR 及必要验证。

本票在 2026-10-15 随已确认的七项拆分建立。历史建立时尚未实施，当前结果以本票Comments及关联PR为准。

## Comments

- 2026-10-15：Ringo 本人在本会话确认测试边界及七项拆票。接票执行前补实际领取时间与状态；本条不作为已执行或验收通过的记录。

- 2026-10-19：[Issue #88 最新 PM 排期结论](https://github.com/DrErwin/hackerthon-bank-agent/issues/88)撤回 10-18 的延期决定，本票保留在 v0.4。分母随实际用例变更重算，旧批次及其 Blocked 状态保持；本条仅更新排期与依赖。

- MAT 范围依据：[Erwin 10-16 结论](https://github.com/DrErwin/hackerthon-bank-agent/issues/133#issuecomment-6199304472)。候选 SEC-T-003/008/012/013/015、N-002/006 按适用性定稿后执行；已定范围不代表改编或实跑已交付。

- 2026-10-19 实施记录：[Draft PR #163](https://github.com/DrErwin/hackerthon-bank-agent/pull/163)依赖#159，先审独立MAT增量，前置合入后须重基main。最小五项材料作为原SEC的v02，新增5实例11行，统一分母137/294/356。64项回归通过，MAT11轮全部Blocked；聊天两项6轮仅局部传输/状态断言通过，另5轮未送达。完整356行20 Passed / 0 Failed / 336 Blocked，原始JSON与指纹已归档。改编和局部实跑已交付，真实检测及入口补验未满足整体关闭条件。
