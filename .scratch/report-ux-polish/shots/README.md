# 报告截图素材（2026-10-30）

真实页面拍摄：真实模型（GLM-5.3 Coding Plan）+ 真实应用流程 + 隔离模拟银行，代码为分支 `codex/report-ux-polish`（本轮文案修正后）。不是固定回复，也不是真实银行。视口 390×844（手机），S01-d 为 1280×800。原像素，未编辑；每张图配同名 `.txt`（卡片文字）。逐张时间、任务和数字见 [manifest.md](manifest.md)。

## 按报告用途

| 用途 | 截图 |
|---|---|
| PPT 开场 / 技术文档 1 项目概览 | [S01](S01-home.png)、[S01-d](S01-d-home-desktop.png)、[S02 大字](S02-large-text.png) |
| 任务完成：转账 | [T01 一句话发起](T01-transfer-one-sentence.png)、[T02 确认单](T02-transfer-confirmation.png)、[T03a 两步验证](T03a-transfer-verify-two-steps.png)、[T03b 刷脸等待](T03b-transfer-face-wait.png)、[T04 回执](T04-transfer-receipt.png)、[T05 聊天改金额](T05-transfer-change-amount.png) |
| 任务完成：账单 | [B01](B01-bills-month.png) |
| 任务完成：减支（订阅/代扣） | [R01 总览](R01-reduce-overview.png)、[R02 退订确认](R02-reduce-unsubscribe-confirm.png)、[R02b 继续办理](R02b-reduce-plan-continue-button.png)、[R03 总回执](R03-reduce-final-receipt.png)、[R02c 先不退了](R02c-reduce-keep-result.png) |
| 创新：生日联动 | [G01 一句话直达](G01-birthday-one-sentence.png)、[G02 配送表单](G02-birthday-delivery-form.png)、[G03 方案](G03-birthday-plan.png)、[G04 留出专款](G04-birthday-earmark-confirm.png)、[G05 下单](G05-birthday-order-confirm.png)、[G05b 付款](G05b-birthday-pay-confirm.png)、[G06 回执](G06-birthday-final-receipt.png) |
| 创新：养老金安排 | [P01 方案](P01-pension-plan.png)、[P01b 储蓄 2500](P01b-pension-transfer1-confirm.png)、[P01c 家人 1000](P01c-pension-transfer2-confirm.png)、[P02 回执](P02-pension-final-receipt.png) |
| 安全自评 2 / PPT 安全 | [X01 卡丢了](X01-lost-card-honest.png)、[X02 验证码进聊天被拦](X02-code-in-chat-blocked.png)、[X04 可疑短信只分析](X04-injection-analyze-only.png) |
| 交互：恢复原任务 | [X03 恢复卡](X03-recovery-card.png)、[X03c 恢复后](X03c-recovery-resumed.png) |
| 技术文档 4 审计 | [A01 管理员时间线](A01-admin-timeline.png)、[A01b 脱敏详情](A01b-admin-event-detail.png) |

## 关键数字（来自页面，不是真实资产）

- 转账：转出 501 元（中风险，验证码+模拟刷脸）、余额 60000→59499；恢复后再转 500 元。
- 减支：退订优酷，每月少扣 25 元；网盘、通信保留。
- 生日：留出 500 元专款，花 199+268=467 元，退回 33 元。
- 养老金：资金 5000 元，留存 1500、转本人储蓄 2500、转家人 1000，并退订网盘 39 元/月。显式启用已批准的 `p01-marked-demo-v1` 演示事实，首句须逐字为批准原话。

## 引用时注意

- 刷脸是管理员页模拟作答，不是真实生物识别；风险判断部分为预设演示场景（页面顶栏已注明）。
- `failures/` 是首次养老金失败（首句非批准原话，安全核对暂停，钱未动），只作缺陷证据，不混入成功素材。
- 模型响应慢：部分卡片之间等待 1—5 分钟，演示视频需剪辑或说明。
