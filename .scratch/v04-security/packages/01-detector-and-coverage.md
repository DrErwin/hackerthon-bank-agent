# 交付包 01：v0.4 检测器与评测完整性（#86 + #88）

Status: in_progress（2026-10-19：追加 #137 读取边界；#86/#88 原实施范围按 PM 最新决定留在 v0.4）
Owner: Ringo；**PM 代行条款**（v0.3 先例，含三要素）：**2026-10-14 24:00 前 Ringo 未确认领取本包，即启动 PM（Erwin）代行**——代行期限至 v0.4 收口，代行期间拆票与实施由 PM 承担、审查人 Erwin（自审如实记录），Ringo 回归即交还；始终如实记录为代行，不冒充 Ringo 本人审查
Activation: 2026-10-11 Erwin 建立（v0.4 正式启动同日）
Start when: #137 按 PM 已定本人读取口径先行；#86 检测器及全量补验、#88 用例扩充与 MAT 按 2026-10-19 最新决定保留 v0.4。原 #84 依赖已关闭，前置满足的票立即推进。
Spec: [v0.4 安全完整性规格](../spec.md)

Accepted by: Ringo（GitHub @RingoDontpanic；本人在本会话明确确认领取）
Accepted at: 2026-10-13（Asia/Shanghai）
Work spec: [Ringo v0.4 安全工作规格](../../v04-ringo-security/spec.md)；[七张实施票](../../v04-ringo-security/issues/)（测试边界与拆分已于 2026-10-15 由 Ringo 本人确认）

Source issue: [#86](https://github.com/DrErwin/hackerthon-bank-agent/issues/86)（真实风险检测器 + 检测层，33 轮 gated；签核项已按 PM 规则豁免）· [#88](https://github.com/DrErwin/hackerthon-bank-agent/issues/88)（安全评测完整性：R06 差 2、8 组 <10、SEC-E-006/v06、MAT 攻击集改编）

## 领取登记（2026-10-13）

Ringo 本人确认领取本包的 #86 检测器工作线及 #88 安全评测工作线，范围沿用本包既定交付要求。确认早于 2026-10-14 24:00 的截止时间，顶部 PM 代行预案的未领取触发条件已解除；本次登记为本人领取。

本轮仅登记接受记录并核对开工条件。Status 保留 ready，开始编写本人规格、拆票或执行时再转 in_progress；accepted 留给联合验收通过后使用。领取不作为实现通过、安全测试通过或 Ringo 专业签核的证据，原 v0.3 例外和 PM 豁免记录保持。

开工 Skill 检查：2026-10-13 本机缺失的 to-spec、to-tickets、implement、code-review 已按团队固定来源 mattpocock/skills 提交 d81f3a183412e71a5b1e84ca21bc1a35eea03a60 安装，并读取各自 SKILL.md 核对。新安装项待下一轮加载；本轮未调用规格、拆票或实施技能。后续按队员开工规范显式选择所需 Skill。

## 2026-10-15 规格与拆票进度

本人工作规格和七张实施票已建立，实际开始日期为 2026-10-15，Status 转 in_progress。Ringo 在本会话确认公开 API / 统一安全执行链加独立模拟银行事实的测试边界，也确认七项拆票的粒度与依赖。

[通知逐项核对](../../v04-ringo-security/notification-audit-2026-10-15.md)覆盖截图五项通知。旧 PR #78 已合并，CI #212 已有后继成功运行，CI #237 的两个末尾空行问题本轮做纯格式修复；旧失败运行保持历史状态。本轮完成规格及正式拆票，代码与评测实施尚未开始。

MAT 改编在 Issue #88 与本包的必交口径不同，已开 [Issue #133](https://github.com/DrErwin/hackerthon-bank-agent/issues/133) 转给 Erwin，仅阻塞 MAT 子项。付费模型补验须在执行前另行确认入口和预算，其他可独立工作按票推进。领取、规格确认及拆票不作为专业签核或联合验收通过。

## 业务目标

v0.3 收口时安全侧的四类明示例外在 v0.4 补齐：真实威胁检测不再是演示开关，评测覆盖达到下限，gated 轮次全部有结论；交付后 v0.3 补验加回，v0.4 收口拿到完整安全证据链。

## 交付范围

1. **检测器与检测层（#86）**：`backend/app/security/` 实现真实风险检测器并接入统一安全执行链路；工具按公共元数据声明权限与敏感等级。
2. **评测完整性（#88）**：`evals/security/` R06 补 2 条、8 个维度组补到 ≥10、SEC-E-006/v06 登记排除项修订、MAT 攻击材料改编接入。
3. **转正复跑**：#84 修复后复跑 SEC-C-001 余 14 轮与 33 轮 gated 全量，结果回填台账。

不在本包范围：#84/#85 底座实现（Erwin 自拆）、账单与前端业务线、v0.3 收口结论改写（补验只新增记录）。

## 向其他工作线提供什么

- 真实风险检测能力（统一安全入口接入，业务线无感复用）。
- 补验后的安全证据（进入 [v0.4 联合验收包](../../v04-bills/packages/02-v04-acceptance.md)）。
- 安全规则变化经公共改动流程通知底座与业务线。

## 验收标准

对应[规格核心验收](../spec.md#2-核心验收)：

1. 检测器交付并接入运行链路，动钱链路的检测不再依赖演示开关。
2. 33 轮 gated 全部转正；余留项如实记录原因与解除条件，不写成通过。
3. 覆盖下限达标：R06 补足、8 组 ≥10、SEC-E-006/v06 修订完成、MAT 改编接入。
4. 证据归档 `evals/security/`（现行台账格式），补验记录与 v0.3 收口例外清单可对照。
5. 一张票一个目录：`backend/app/security/` 与 `evals/security/` 分票；底座接缝改动登记依赖。

## 负责人接受后怎样拆自己的票

- Ringo 接包（或 PM 代行）后走 `to-spec → to-tickets`，在本人 `.scratch/` 工作组建立规格与实施票，回填本包 `Work spec`。
- 顺序建议：检测器规格 → #88 用例扩充（不依赖 #84，先行）→ #84 完成后集中复跑转正。
- PM 代行时同样按单目录拆票，票据与验收记录注明代行。

## 2026-10-19 最新排期与追加范围

[Issue #86 最新决定](https://github.com/DrErwin/hackerthon-bank-agent/issues/86#issuecomment-6260282588)和 [Issue #88 最新决定](https://github.com/DrErwin/hackerthon-bank-agent/issues/88#issuecomment-6260283007)撤回 10-18 延期裁定，检测器、全量补验及覆盖完整性均留在 v0.4。七张原票保留编号，前置已满足即按票实施；真实模型仍需入口与预算确认。122 / 274 / 330 是变更前基线，新增用例后按实际规模重算，历史报告保持。

MAT 范围已由 [#133](https://github.com/DrErwin/hackerthon-bank-agent/issues/133#issuecomment-6199304472)明确为最小集合适用项必交，额外扩充可选；范围待定依赖解除，实施与观察端条件保持。当前追加 [v04-ringo-security/08：账单读取安全边界与声明冻结](../../v04-ringo-security/issues/08-bills-read-security-boundary.md)，业务规则沿用 [#137 临时决定](https://github.com/DrErwin/hackerthon-bank-agent/issues/137#issuecomment-6250123462)。账单审计整改仍由 [#145](https://github.com/DrErwin/hackerthon-bank-agent/issues/145)的账单负责人独立实施。领取、AI 辅助复核、真人签核与联合验收分别记录。
