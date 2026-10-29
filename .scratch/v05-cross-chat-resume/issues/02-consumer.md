# 02：API明确消费普通聊天resume建议

Ticket ID: v05-cross-chat-resume/02
Package: [v05-cross-linkage/packages/01-platform-bank](../../v05-cross-linkage/packages/01-platform-bank.md)
Spec: [普通聊天继续原任务：API消费](../consumer-spec.md)
Core scenarios: C201—C205
Type: 开发
Owner: Erwin（v0.5）；执行 transfer_pause_recovery AI 子代理
Directory: backend/app/api/
Status: implemented_pending_merge
Blocked by: [v05-cross-chat-resume/01：平台无字段继续建议](01-provider.md)，[PR #357](https://github.com/DrErwin/hackerthon-bank-agent/pull/357) 已合入 bbfb6fd045dd6070f2928d366519d492dfd37849，本票已重放到该主线基线
Accepted by: 根明确委派，依据用户本轮完成非比赛资料与真实页面走查修补授权
Accepted at: 2026-10-29
Branch: codex/v05-api-cross-chat-resume-02
Verification: 真实Cross/Harness/ASGI HTTP/模拟银行，规划为替身；consumer红源必须已包含明确provider合同。验证同原任务、重复receipt、写入中断读回及当前授权门，准确记录源与XML，不操作运行库。
Evidence: [消费验证](../consumer-verification.md)、[原始结果及逐项来源](../consumer-verification.json)、[依赖重放证明](../consumer-rebase.json)

- [x] 同一原父任务收到resume而非query，后续选择来自真实业务状态。
- [x] 原请求receipt重复或中断不重新推进，不新增银行写。
- [x] 当前版本/线程/身份/会话/recovery/allowed及专用确认验证门保持。
- [x] 局部验证、两轴、CI、合入与真实页面复验分开记录，作者不合并。

## 交付事实

固定生产源 affd96d289f60841396b05e5e6729c960a3de2b1；新测试断言修正源 7d9d817ee4d29251d8cdf31094be2413a261ece9。必要组合原批 43 pass / 1 新断言错误，同一失败节点修正后 1 pass；支持 44 个唯一节点，并非一次 44 全绿。独立 Spec 已报 0 剩余必须项；Standards、精确 PR head CI、合入与原页面复验按各自记录判定。
