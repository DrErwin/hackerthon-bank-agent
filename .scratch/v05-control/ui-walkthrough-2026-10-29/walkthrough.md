# 从空白聊天开始的实际页面走查（2026-10-29）

Status: partial / live-model-blocked — 新500元转账及刷新核对完成，减支原计划经重新登录/专用恢复后办结；三个修复PR均已合入。生日两次真实入口失败，最小模型请求60秒读超时，后续流式诊断HTTP429/1302；已停止继续live调用，生日/P01及普通聊天resume页面尚未完成。

用户要求先清聊天、从头走查。当前Shell没有删除/新聊天按钮，也没有公开删除聊天接口；本轮通过既有公开POST /threads准备空白新对话，页面重载后实际显示0条回复、0项办理。**旧聊天没有硬删**，原交易回执与银行数据保留；不是整体重置。[准备记录](fresh-conversation-setup.json)、[空白首页](01-blank-conversation.jpg)。

## 实际环境

- 浏览器：本对话现有IAB标签1，实际元数据与DOM均为 `http://127.0.0.1:5190/`。页面已连接；本轮未声称原Edge原生网址识别或本人手动确认已完成。
- 接口：5191真实本地API；真实模型理解、真实应用流程及隔离MockBank，非contract-demo固定回复。前段bb6228bd，356后17f7ef2c；357/358全合后运行ffa42936，后端树d27249f6d2fd9bd5b568630f59c45b6f93c027cd。前端树始终3fe1279c8e17b7e3b59ee441949958085f556cd4。每段来源与截图元数据分别记录，银行未重置。
- 原隔离轮次 `http-live-40cedee160da`，新thread `2c73cc0b-5449-436f-b67d-7ef60977b618`；旧转账 `fdf2090d-ef3b-4808-bc2e-def20c2bc267` 已明确取消；新500元转账 `0046b191-c405-49c2-80e7-8d5736335bf8` 已成功。
- 银行原基线A1=1500元、A5=2500元、冻结0，原P01三成功操作保留。13:27本轮新转账成功后A1=1000元、A5=2500元，冻结0。其后新增视频退订，未新增转账。[只读基线](bank-baseline.json)、[独立观察与26变体适用范围](bank-observations.md)。

## 已实际走过

| 场景 | 实际结果 | 证据 |
|---|---|---|
| 空白新对话 | 0助手回复、0任务；欢迎卡与输入框可用 | 01图片与准备JSON |
| 普通聊天查本月开支 | 原话“你好，我想看看这个月都花了多少钱，主要花在哪儿。”；选择全部本人账户，消费84元，转出3500元/转入7500元单列 | [汇总DOM](02-monthly-bill-summary.txt)、03图片 |
| 分类展开及键盘收起 | 其他分类为39+20+25三笔，共84元；在原卡内展开，再用Enter收起；后续业务开始后账单折叠为可展开已办结卡 | 浏览器实际DOM；04以后原账单状态仍可见 |
| 普通转账保留事实 | “我想给妈妈转500元。”→显示A1/A5余额卡；选A1后保留妈妈/500元，进入确认，未批准资金 | [选卡截图](05-transfer-bank-cards.jpg)、04/06 DOM |
| 确认前UI改金额 | 500→600，仍同task，生成新操作/确认版本；付款卡/妈妈保留 | 07—09 DOM及独立观察 |
| 聊天改金额 | “金额改成500元。”回到同task的500元新确认v3；job约58.65秒后成功，不把工具selector deadline当产品失败 | 10a/10c DOM及独立观察 |
| 聊天与卡片并存 | 待确认时“我有哪些收款人？”只读列出联系人；原500确认保留，可从顶部当前办理回原卡 | [11 DOM](11-payee-query-during-confirmation.txt)、12图片 |
| 新卡缺风险证据 | 改A5/500不在已批准standalone事实内，正确暂停，零新银行写 | [14 DOM](14-unapproved-funding-source-pauses.txt)、独立只读观察 |
| 暂停返回缺陷 | 点“查看原任务”仍回同卡；编辑0、取消0、查看原任务1。实际红断言已执行，不能记通过 | [红计数](16-recovery-controls-before.json)、[红截图](16-paused-transfer-loop-before-fix.jpg)、15/16 DOM |
| 大字与窄屏 | 应用大字切换；390×844视口根宽390、无根横向溢出。仅这一实际状态，不代表所有页面或真实手机 | [18截图](18-narrow-viewport-large-text.jpg)、[布局值](18-narrow-viewport-layout.json) |
| 记录与键盘返回 | 还没办完筛选只保留待办；Shift+Tab焦点仍在抽屉，Escape动画结束后关闭并回焦记录按钮 | [19截图](19-mobile-pending-records.jpg)、[键盘最终事实](19-dialog-keyboard-settled.json) |
| 恢复显示 | 标准字与默认865×764视口已恢复 | 20 DOM及截图清单内视口元数据 |
| 原转账暂停恢复 | PR356后同任务进入可编辑/取消等待，A5/500事实保留；重查A5仍暂停，未放行未批准组合 | 32—38 DOM及观察 |
| 严格演示边界与取消 | 旧任务累积额外话语，改回A1仍缺覆盖；未扩大白名单，明确取消。该旧任务5个操作均无银行写 | 38后DOM及观察 |
| 新500元实际闭环 | 新任务选A1，专用确认、验证码、独立管理员模拟人脸；银行成功500元、费0、A1可用1000元 | [成功截图](44-transfer-success.jpg)、[刷新后截图](46-success-after-refresh.jpg) |
| 成功刷新无重复转账 | 实际页面刷新前后15项独立银行比较一致；4个银行操作、4条操作关联流水，单次新500元，旧P01三笔保留 | [刷新前](bank-before-refresh.json)、[刷新后](bank-after-refresh.json) |
| 浏览器缩放能力探针 | Control+Equal后宽865/高764/dpr1.5/cssZoom1/visualScale1均未变；不能记200%通过 | [实际测值](47-browser-zoom-capability-probe.json) |
| 自然减支目标 | 最近完整月9月284元、比8月多100元；按原话保留通信套餐，选择视频25元退订，专用确认和验证码后银行退订成功，下期停止，无退款 | 48—50 DOM |
| 减支父计划续办缺陷 | 子任务已成功，父任务仍running/3/4并允许resume；聊天“继续”被拒绝，不能记整个目标成功 | [只读快照](cross-parent-snapshot.json)、[实际聊天](51-reduction-continue-result.txt)、[原始截图](52-reduction-parent-continuation-blocked.jpg) |
| 实际登录过期 | 原会话自然到期后，横幅“登录已过期”、重入入口出现，聊天输入及发送禁用；未通过聊天绕过登录或恢复 | [57 DOM](57-session-expired-before-service-update.txt)、[过期原图](57-session-expired-disabled-input.jpg) |
| 原减支父计划恢复及办结 | 实际专用重新进入后，原任务仍须点查看原任务；恢复同parent4/4，保留通信并出总回执，每月下期少扣25元。parent succeeded/rev9，原视频银行操作仍1次 | [59恢复](59-original-reduction-recovered-after-login.txt)、[60办结图](60-reduction-plan-completed-after-session-recovery.jpg)、[银行只读结果](bank-after-reduction-and-birthday-errors.json) |
| 生日普通入口失败 | 14:38“500元以内给妈妈安排花和蛋糕。”失败后查原job确认无候选，再于14:42明确生日日期；两次均error_completed/MODEL_PROPOSAL_FAILED，模型60390/60172毫秒；零生日任务、冻结、订单或支付 | [61首句](61-birthday-initial-model-failure.jpg)、[62明确日期](62-birthday-explicit-date-model-failure.jpg)、同银行只读结果 |
| 原模型最小诊断 | 同配置只发“只回复OK”，无工具/历史/银行资料，60562毫秒OpenAITimeoutError→APITimeoutError→ReadTimeout；GETmodels 200/578毫秒且模型存在。不能据此断言供应商排队/额度/具体网络根因 | [原始安全诊断](../../v05-live-model-diagnostic/2026-10-29-minimal-probe.json) |
| 限时连接分层诊断 | 同provider/同模型、无业务资料，单次流式检查672毫秒HTTP429/1302、0chunk；说明该时点速率限制拒绝，不能倒推此前生日超时的唯一根因，更不等于CI账号计费问题 | [流式诊断](../../v05-live-model-diagnostic/2026-10-29-stream-probe.json)、[诊断结论](../../v05-live-model-diagnostic/diagnosis.md) |

截图和DOM均由本轮真实页面直接保存，原像素保留。[截图清单](screenshots.jsonl)、[状态清单](states.jsonl)。02/12/53/55等视口只显示卡片的一段，文件名不代表整卡已入图；55主要显示父计划上段，不能证明其中退订结果可读。后段为留图将真实视口调到1100×1200；[56转账结果](56-transfer-success-receipt-readable.jpg)可读成功金额、手续费、时间及余额，优选为该业务结果图；不是200%缩放，不拼接伪造。

## 修补与当前缺口

[PR356](https://github.com/DrErwin/hackerthon-bank-agent/pull/356) 已合并17f7ef2c。仅明确提交前、独立转账、准确ADMISSION风险覆盖缺失才回到可修改/取消等待；旧END恢复核对可信检查点和当前绑定，不以无回执推定安全。两位非作者独立Standards/Spec审查均0必改；108个唯一受影响测试通过。精确PR head的CI因账号计费未启动，仍是blocked，不是CI通过。

减支续办缺口的[PR357](https://github.com/DrErwin/hackerthon-bank-agent/pull/357)提供者、[PR358](https://github.com/DrErwin/hackerthon-bank-agent/pull/358)API消费者均已双轴0必须项后合入。平台124项通过，API44个必要节点为43过加新测试断言修正后同1补验；不是一次44绿，两组存在重叠不相加。只补当前唯一、允许续办、RUNNING无交互卡的无字段resume，保留所有业务门。原模型候选未持久化，不编其具体动作或错任务。详见[固定源码/审查/CI/合入](code-review-and-merges.md)。

原减支父在会话过期后通过F11恢复并完成，未重复退订；**这不是普通聊天resume已页面通过**。后者仍须在同会话、非交互RUNNING阶段实际说“继续”验证。当前模型最小请求也读超时，不能把两个生日入口失败单归于话术，也不能用固定回复或旧HTTP批填作新页面通过。

## 未完成及证据边界

- 本轮新500元转账已实际成功并刷新核对；旧转账恢复后取消，两个任务证据分别保留。
- 减支父计划已经原号完成。生日与本轮新P01、普通聊天resume真实页面及其余变体尚未完成；当前模型实际读超时，后续独立流式探针又遇速率限制，已停止反复调用。旧银行余额不足新P01，另备5200/5201同一fresh round/data已更新ffa且未操作业务；[初态审计筛选勘误](../ui-goals-fresh-20261029/restart-readiness-pension-erratum.json)确认养老金1条、A15000/A50、零任务/银行操作。不能混成同轮成功。
- 应用大字、390视口、AX/DOM和键盘检查不代表200%真实浏览器缩放、完整读屏、真机或本人安全/体验接受；这些仍另记。
- 所有截图含明确演示风险说明；有限真实危险检测和获批演示事实边界保持，缺风险证据不放行。
- 未制作比赛说明/PPT/提交包，未处理CI账号付款或更改额度，未重置/硬删银行与旧聊天。

## 归档核对

适合选用的原图包括01空白起点、05选卡、31账单口径、56转账结果及60减支办结；失败/过期画面仅作缺陷与恢复证据，不混成成功图。最后恢复标准字与865×764视口，实际64状态确认输入可用；63只是reset后的中间记录，名称不表示尺寸已生效。

本批只做文档/证据核对，不为归档重新跑代码或CI。[本地链接检查](link-checks.json)、[配置凭据与验证码文本扫描](artifact-checks.json)、[逐文件SHA256清单](artifact-manifest.json)一并保存；图片保留原像素，没有做OCR秘密扫描或编辑。8份文本采用Windows CRLF，保留原字节与审查hash；识别CRLF的空白检查通过（仅本次命令加cr-at-eol，不改Git配置），不是默认diff-check无输出。2026-10-29 15:07核远端open PR=0；受保护D盘主目录仍原9a479ea4及原未跟踪原型，没有reset/clean/切分支或盲目暂存。
