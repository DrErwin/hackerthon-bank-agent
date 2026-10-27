# frontend-design-system/02：让对话带着用户办理

Ticket ID: frontend-design-system/02
Package: 用户在本对话直接授权的前端体验改造（2026-10-26）；沿用 frontend-design-system 工作组。
Spec: [设计系统规格](../spec.md)
Type: 开发
Owner: Erwin
Directory: `frontend/`
Status: ready_for_review — 实现、局部测试、浏览器走查与 AI 审查已完成，等待体验接受与合入。
Accepted by: 本对话 AI，依据用户“同意，改造吧”
Accepted at: 2026-10-26
Blocked by: [frontend-design-system/01：统一设计系统并接入常用组件](01-foundation.md)（实现已可复用，合入依赖 PR #318）

## 业务结果与核心场景

- C01：进入即看见对话与常驻输入框。快捷入口向同一段对话表达需求。
- C02：转账时在对话内选收款人、金额、付款卡；当前只出现一个填写步骤。已填资料可回看和修改。
- C03：中途查资料仍保留原任务；顶部简短摘要可回到原任务。办理记录使用抽屉。
- C04：助手回复在正文可读；每个任务保持一份可操作卡片，旧确认保留只读限制。
- C05：确认、验证、结果、断线和恢复沿用服务端状态，重要事实和错误持续可见。
- C06：手机优先、电脑适配；大字、键盘、抽屉焦点及长内容可用。

## 实施边界

保留已选 shadcn / Radix / Vaul / Lucide / Sonner。只改前端呈现、前端契约演示和相应测试。真实自由对话仍原样发给现有 Agent；前端不猜测交易意图、不代理执行、不复制银行规则。契约演示中的固定文本解析仅服务可操作原型，不算模型理解证据。账单、订阅和联动继承新的对话容器，业务细节保持现有公开能力。

## 验收与证据

- [x] 前端测试 113 项及构建通过，包含按服务端要求填写、同名歧义、旧确认只读、刷新后历史子记录缓存复用。
- [x] 手机/电脑走查转账选择、修改、查询穿插、确认及回执；实际范围见验证记录。
- [x] 新原型复用当前前台，原 5187 手机入口指向 5189 的稳定预览；旧方案保存为 phone-v1.html。
- [x] AI 审查、CI、真实 API/模型验证分别记录。

验证：[02 对话改造证据](../verification-02.md)。确认与结果使用既有安全边界；真实自由语言/真人适老化验收仍需后续联调。

交付：[Draft PR #319](https://github.com/DrErwin/hackerthon-bank-agent/pull/319)，依赖 PR #318。
原型快照：[codex/frontend-agent-prototype-20261026](https://github.com/DrErwin/hackerthon-bank-agent/tree/codex/frontend-agent-prototype-20261026/.scratch/frontend-ux-prototype-20261026)（提交 `a820ba7`，不合入主线）。

基线：`a69ebc9`。分支：`codex/frontend-agent-conversation-02`。后继 Draft PR 以前序设计系统分支为目标，保持单票可审查。
