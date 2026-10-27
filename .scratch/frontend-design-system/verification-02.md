# frontend-design-system/02 验证记录

2026-10-26。基线 `a69ebc9`（前序 Draft PR #318）；用户已在本对话明确同意对话驱动改造。

## 实际交付

对话正文恢复可读的助手回复；同一任务保留一个可操作卡片，跟到最新相关回复。常驻输入框、工具抽屉、当前任务摘要和历史根记录共享原任务。转账按服务端当前字段显示填写控件；同名候选仍显示已填金额、付款卡和修改入口。完成子明细归入原查询记录，打开缓存结果不再发起业务调用。

保留 shadcn / Radix / Vaul / Lucide / Sonner 设计系统。账单、订阅、生活安排沿用原业务插槽；本次没有扩展其后端能力。前端真实自然语言原样送给既有 Agent，固定文本解析只存在 contract-demo。

## 本地检查

- 最终 `npm test -- --reporter=dot`：13 文件、113 项通过（20:38 开始）。
- `npm run build`：默认真实 API 模式通过；`VITE_API_MODE=contract-demo npm run build` 也通过。
- `git diff --check`：通过。
- Impeccable detector 对 AssistantPage、ConversationTools、conversation.css 返回 `[]`，属于机械检查。
- 默认构建主包约 550 KB，gzip 170 KB；契约演示包约 565 KB，gzip 174 KB。仍有构建器默认大包建议，本票未改路由拆包。

新增/调整的有效回归：

1. 点选、查余额、文字改金额沿同一演示任务；旧确认失效，新确认只有一组动作。
2. `payee=null` 且服务端要求金额/付款卡时，界面跟随服务端，避免反复选人。
3. 同名收款人候选时，已填金额、付款卡与修改入口保留。
4. 从记录打开结束的根任务；从顶部继续被折叠的订阅子任务，展开分组并聚焦。
5. 刷新后完成子任务归入根记录；重新打开缓存子结果，`cardAction` 调用次数为零。

## 浏览器实际走查

- 1280×720 桌面及预览中的 390×780 手机 iframe；原型外框缩放为 0.75 展示，内层真实 CSS 视口为 390px。
- 在 5188 契约演示中：创建转账、选择收款人/付款卡、填 500 元、中途查余额、说“改成300元”，确认后经过专用验证码与独立管理员模拟人脸，最终显示 300 元成功回执。期间刷新触发恢复卡，再读取原任务继续验证。
- 在 5189 稳定构建中：按修正后的服务端字段顺序填写，账户/金额仍在，收款人可选。输入框保持可用。
- 手机工具抽屉 Esc 关闭后，焦点回到“查资料 / 办业务”（DOM 实际确认 true）。
- 手机标准字号输入 18px、大字模式 20.25px；两种情况下根元素 clientWidth/scrollWidth 均为 390px。最终账户、金额、收款人姓名均 18px；发送按钮高 56px。
- 恢复卡删除“已处理 · 只读”，明确仅表示上次资料已找回。

截图均实际打开核对：

- [手机初始对话](evidence/conversation/home-mobile.png)
- [手机当前步骤](evidence/conversation/mobile.png)
- [电脑恢复后继续](evidence/conversation/desktop.png)
- [手机工具抽屉](evidence/conversation/drawer-mobile.png)
- [对话回看](evidence/conversation/conversation-mobile.png)
- [300 元回执内容](evidence/conversation/receipt-desktop.png)（截图上方标题超出视口；成功状态由同次浏览器可访问树确认）

## AI 审查

- Standards：1 项，继续前展开祖先分组。修正后原审查者复核 resolved。
- Spec：3 项，真实字段顺序、同名歧义保留摘要、完成历史记录可达。原审查者最终复核全部 resolved。
- 独立视觉 finish：2 项，核心资料 18px、恢复徽标含义。修正并更新手机/电脑截图后 disposition `ship`。补充 PRODUCT.md 记录用户已确认产品事实。

以上是 AI 审查，不是用户体验接受或真人安全签核。

## 证据范围与交付

本次为前端实现和契约演示验证。实体手机软键盘、200% 浏览器缩放、完整读屏、真实 API / 模型整条对话路径尚未在本票运行。后端文案、自由对话理解与跨业务执行能力继续按各自实现验收。

交付为 [Draft PR #319](https://github.com/DrErwin/hackerthon-bank-agent/pull/319)，以前序 PR #318 分支为目标。代码提交 `31e9ce8` 的 Repository checks（run `40324901283`）未启动，平台返回账号账单支付失败或需要提高支出额度；属于平台阻塞，不能写成代码检查通过。PR #318 也仍待合入。

预览：`http://127.0.0.1:5189/conversation-preview.html`；原静态入口 `http://127.0.0.1:5187/phone.html` 已更新指向该构建。启动方式：设置 `VITE_API_MODE=contract-demo`，运行 `npm run build`，再运行 `npm run preview -- --host 127.0.0.1 --port 5189`。原型使用虚构资料和固定回复。
