# 21：P01显式profile与完整来源接线

Ticket ID: v05-birthday-platform-dependencies/21
Package: [平台与银行公开契约](../../v05-cross-linkage/packages/01-platform-bank.md)
Spec: [P01显式profile与完整来源](../pension-profile-wiring-21.md)
Type: 开发
Owner: Erwin；Codex按中控分派
Directory: backend/app/agent_platform/
Status: developed — 483平台回归/13既有skip、189安全边界、API22后6项准确组合通过；待两轴与CI，非真人接受
Accepted at: 2026-10-27
Accepted by: Erwin本轮分派；用户已明确批准两笔限定演示范围，非最终安全接受
Blocked by: 无当前实施前置；19/20及实际发现的API22均已合；真实模型/页面验收由中控后继
Source issue: 既有[Issue #345](https://github.com/DrErwin/hackerthon-bank-agent/issues/345)的可信来源边界；不代本票新开批准范围

本组20已交安全提供方，21由本轮分派独立占号，只有平台源码和本组票据。

- [x] P21-1 默认关闭/显式literal/进程flag/错误脱敏且不写原配置。
- [x] P21-2 新根/子任务完整capture来源、19真实绑定与hash、重启保留。
- [x] P21-3 缺任何capture的历史不继承演示、不回填，旧A2保持。
- [x] P21-4 真API/Harness/安全/银行+脚本模型的P01两笔逐笔确认和双因子闭环。
- [x] P21-5 危险/未知/异参零未授权资金，重启原号无重复提交。
- [ ] 必要红绿、受影响回归、独立PR交中控两轴；不代签本人接受/不自merge。

[准确source、递进失败/通过、原证据与边界](../pension-profile-wiring-21-verification.md)。原960失败与广回归记录不被API22后的6项小组合替代，原pytest失败库被自动清理的事实也明确保留；新的红/绿独立basetemp数据库已留存。
