# 21：P01显式profile与完整来源接线

Ticket ID: v05-birthday-platform-dependencies/21
Package: [平台与银行公开契约](../../v05-cross-linkage/packages/01-platform-bank.md)
Spec: [P01显式profile与完整来源](../pension-profile-wiring-21.md)
Type: 开发
Owner: Erwin；Codex按中控分派
Directory: backend/app/agent_platform/
Status: in_progress
Accepted at: 2026-10-27
Accepted by: Erwin本轮分派；用户已明确批准两笔限定演示范围，非最终安全接受
Blocked by: 无实施前置；19/20均已合；真实模型/页面验收由中控后继
Source issue: 既有[Issue #345](https://github.com/DrErwin/hackerthon-bank-agent/issues/345)的可信来源边界；不代本票新开批准范围

本组20已交安全提供方，21由本轮分派独立占号，只有平台源码和本组票据。

- [ ] P21-1 默认关闭/显式literal/进程flag/错误脱敏且不写原配置。
- [ ] P21-2 新根/子任务完整capture来源、19真实绑定与hash、重启保留。
- [ ] P21-3 缺任何capture的历史不继承演示、不回填，旧A2保持。
- [ ] P21-4 真API/Harness/安全/银行+脚本模型的P01两笔逐笔确认和双因子闭环。
- [ ] P21-5 危险/未知/异参零未授权资金，重启原号无重复提交。
- [ ] 必要红绿、受影响回归、独立PR交中控两轴；不代签本人接受/不自merge。
