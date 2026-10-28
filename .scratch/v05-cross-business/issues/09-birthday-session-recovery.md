# v05-cross-business/09：生日敏感等待的新会话恢复

Ticket ID: v05-cross-business/09
Package: [v05-cross-linkage/packages/03-cross：三个生活目标编排](../../v05-cross-linkage/packages/03-cross.md)
Spec: [联动业务规格](../spec.md)，[安全依赖与失败证据](../session-recovery-09.md)
Type: 开发
Owner: Erwin（v0.5 统一负责）
Directory: `backend/app/modules/cross/`
Status: merged — PR341，bb6228bd6f96b8c5aaf2dd43abcd659da01bed86；两个原must及observe分支闭合，最终自动核查见根集成记录，页面另待
Blocked by: 无实施前置；平台23（PR #353）已合入本轮基线 `bec56218`，只读提交事实消费见[审查修补](../session-recovery-09-review-fixes.md)。既有平台18（PR #344）、17（PR #342）及16（PR #343）已合入受测主线 `ed1596d5`。前置[平台票13](../../v05-birthday-platform-dependencies/issues/13-session-recovery-proof.md)（PR #335）与安全 PR #330 已合入 main `30cbe740`
Accepted by: 本对话 AI，依据 2026-10-27 用户完成非比赛资料任务授权及中控委派
Accepted at: 2026-10-27
Core scenarios: XL-B 敏感等待恢复、XL-X 会话/权限与重复执行
Verification: 真实 Harness/Cross/存储/安全/模拟银行，规划器为明示替身；旧卡拒绝、新会话新版本、旧挑战不复用，未知沿原号核实。局部组合不写作真实模型/页面/真人安全验收。
PR: [已合 #341](https://github.com/DrErwin/hackerthon-bank-agent/pull/341)。固定5810d67e：root Standards与独立Spec均0剩余必须项，精确head CI计费未启动；根合入bb6228bd，backend与488受测树一致。[10-28精确分层验证](../session-recovery-09-closeout-28.md)、[同源真实模型/HTTP中断取消](../../v05-control/freeze-recovery-http-2026-10-28.md)及[原208历史范围](../session-recovery-09-final-verification.md)分别保留；不是页面或真人安全接受。

## What to build

生日冻结、下单、核销的确认/验证等待恢复应从本模块 SOP 重查当前安全门，不回缓存旧会话卡。新会话必须新确认/验证；不能在平台篡改 Cross 私有状态，不能移除安全限定授权的唯一性与身份检查。

已执行或未知仍核实原操作；不能盲换 operation、重冻或退款。未提交且安全证明可撤离时，消费安全方明确的退休/新尝试接缝。

## Comments

- 2026-10-27：中控安排本票在平台票12之后完成；先以真实组合保存冻结旧卡与限定授权冲突失败，安全最小接口需求另文，未修改安全状态规则。
- 2026-10-27：中控明确续作本票生产消费。基于最新 main 保留 #332/#334；原始 1fail/1pass 不覆盖，按续作规格 R09-1—4 验证。全局进度、合并与独立两轴审查由中控负责。
- 2026-10-27：Draft PR #341。Cross 源码在 `57a6958b` rebase 到 main `9f4b73b1` 后为 `31c2cedf`，本目录树均为 `a4ef3b8631562c82bfead5b43b6e3609f3835b05`；本次 rebase 无代码差异。补锁后2个定向已过，21个恢复与32个预算结果的补锁前范围及仍失败的依赖均在规格记录，不冒称最终全套。
