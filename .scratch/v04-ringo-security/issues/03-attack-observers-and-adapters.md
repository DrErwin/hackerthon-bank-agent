# v04-ringo-security/03：检测与攻击观察评测接入

Ticket ID: v04-ringo-security/03
Package: [v04-security/01：检测器与评测完整性](../../v04-security/packages/01-detector-and-coverage.md)
Spec: [本人工作规格](../spec.md)
Core scenarios: RS01、RS04、RS05、RS10
Type: 开发
Owner: Ringo
Directory: evals/security/
Status: blocked（仍在 v0.4，范围已定，等待所列技术前置）
Blocked by: [v04-ringo-security/02：真实风险识别与安全门组合](02-real-risk-detector.md)；33 轮各自所需的资料入口与攻击观察公开能力（提供方按真实缺口登记）
Source issue: #86（[#86](https://github.com/DrErwin/hackerthon-bank-agent/issues/86)、[#88](https://github.com/DrErwin/hackerthon-bank-agent/issues/88)）
Verification: 对每类门各运行合法对照和攻击样本，核对实际输入、裁决与工具调用；资金相关实例同时检查独立银行提交/流水。先验证本票，再在所需路径就绪时联调；真实模型执行留到 /07。

## 交付结果

为原 9 轮真实检测、3 轮资料入口及 21 轮攻击观察分别提供可核查的运行与判定，已具备路径及时联调。

## 验收条件

- [ ] 优先复用现有 run_instance、共享轮及公开 API，不新建另一套安全执行器。
- [ ] 三类能力门分别探测及记录；删除静态 gate 标记不作为能力交付证据。
- [ ] 实际请求到达检测器及必要模型/工具边界，判定与银行副作用有独立观察。
- [ ] 跨用户拒绝保持资源存在性隐私；工具返回注入不能改变权限与确认规则。
- [ ] 隔离资料和受控观察不能扩展成真实 Shell 或任意外发能力；缺失时记 Blocked 并标提供方。
- [ ] 已完成适配路径先局部验证，未满足前置的轮次不提前转 Passed。

## 实施边界

本票只修改 Directory 指定目录。开发或编写运行代码时使用 implement；有代码时按 code-review 分别核对仓库规范与本票要求，实际测试和本人批准分别记录。纯文档按仓库例外做内容检查；代码和执行配置走独立 PR 及必要验证。

本票在 2026-10-15 随已确认的七项拆分建立。当前未开始实施，最终交付以本票实际证据为准。

## Comments

- 2026-10-15：Ringo 本人在本会话确认测试边界及七项拆票。接票执行前补实际领取时间与状态；本条不作为已执行或验收通过的记录。

- 2026-10-19：[Issue #86 最新 PM 排期结论](https://github.com/DrErwin/hackerthon-bank-agent/issues/86)撤回 10-18 的延期决定，本票保留在 v0.4。分母随实际用例变更重算，旧批次及其 Blocked 状态保持；本条仅更新排期与依赖。
