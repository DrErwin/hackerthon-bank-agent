# v05-cross-chat-resume/01：平台无字段继续建议

Ticket ID: v05-cross-chat-resume/01
Package: [v05-cross-linkage/packages/01-platform-bank：公共平台与银行](../../v05-cross-linkage/packages/01-platform-bank.md)
Spec: [已授权规格](../spec.md)
Type: 开发
Owner: Erwin（platform_completion子代理）
Directory: backend/app/agent_platform/
Status: merged — PR357 / bbfb6fd045dd6070f2928d366519d492dfd37849；两非作者双轴0必须项，精确CI计费未启动
Blocked by: None；基线origin/main17f7ef2c
Accepted by: 用户本轮授权及中控明确分派
Accepted at: 2026-10-29
Core scenarios: R1—R3；XL-S普通聊天继续原父任务
Verification: 真实planner工具绑定+Harness验证、明确固定模型；不运行真实页面/模型/旧银行

## What to build

仅补无字段resume建议schema、必要当前状态验证与模型续办提示。保留原消歧、身份、
版本、allowed、未知查询及确认/验证码专用门。消费者接口见spec，API另作者独立交付。

## Evidence

根原失败位于运行工作树 `.scratch/v05-control/ui-walkthrough-2026-10-29/`
的51-reduction-continue-result.txt与cross-parent-snapshot.json；本票仅引用不改写。
确定性红绿及固定head/JUnit随后续记，局部测试不算真实模型/页面通过。

作者验证见[固定源码、124项与消费者接缝](../verification.md)。API consumer另作者
独立PR依赖本票；本票不改API、不运行旧银行、不自行合并。

根已合入，API consumer PR358亦已另票合入。[审查、CI及页面分层](../../v05-control/ui-walkthrough-2026-10-29/code-review-and-merges.md)：原父在重登录后经专用F11恢复并完成，不冒作普通聊天resume页面通过；后续真实模型最小请求读超时，聊天续办页面仍待。
