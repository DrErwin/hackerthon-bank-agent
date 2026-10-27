# v05-birthday-platform-dependencies/11：生日普通输入发布中断后续原请求

Ticket ID: v05-birthday-platform-dependencies/11
Package: v05-cross-linkage/packages/01-platform-bank；2026-10-27 非资料任务收口
Spec: [原规格](../spec.md)；[本轮授权与分派](../../v05-control/non-material-closeout-2026-10-27.md)
Type: 开发
Owner: Erwin
Directory: `backend/app/api/`
Status: ready_for_review — 7项故障恢复检查、API目录232项通过；依赖PR323，待两轴审查与合入
Accepted by: 本对话 AI，依据用户 2026-10-27 明确要求完成非资料任务
Accepted at: 2026-10-27
Blocked by: v05-birthday-platform-dependencies/10 的原输入转换只读查询接缝
Core scenarios: 生日普通输入的发布失败、HTTP回执中断、原号重试、异参/异主体拒绝；原转账/订阅/预算/受控编辑兼容

## 交付结果

用户提交生日预算/日期等普通输入后，若平台已有原请求的持久转换事实，技术中断可沿同 request_id 续做；已经发布的请求返回原封存结果，不把后来新卡冒充原回执。没有原转换事实的其他输入不因本票自动重放。

## 验收与验证

- 通过真实 HTTP 与现有本地组合，注入封存、任务发布或回执保存断点；同请求恢复不创建第二转换、不重复历史/SSE或银行写入。
- 同 request_id 改参数仍409；旧交互的新请求、其他用户/会话、无持久转换的请求仍拒绝。
- 原赢家存在而任务已有后继时，只返回原结果，不将旧结果重新发布为当前卡。
- 复用平台原请求查询和现有请求HMAC摘要，不复制转换摘要算法、不跨目录补状态。
- 局部回归、受影响API检查、规范/规格独立审查；真实模型/页面/银行验收另票留证。

## 验证记录

受测 `07eb319f`（平台代码 `5aae44b6`）：新文件7 passed；API目录232 passed / 0 failed，461.19秒。原基线已真实复现发布报错后同request永远503。API保存原完成TaskView后稳定发布，平台pending按原UUID恢复；后继已推进时不重新广播旧卡。证据见[API11验证](../api-input-recovery-verification.md)。
