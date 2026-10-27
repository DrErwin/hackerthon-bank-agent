# 19：转账风险检查保留可信父请求来源

真实P01子转账只有内部marker，未把父原话交给安全检测。[Issue #345](https://github.com/DrErwin/hackerthon-bank-agent/issues/345) 转给Erwin。本轮用户要求完成非资料任务；root在平台16交付后顺序领取，实施仅 `backend/app/agent_platform/`。

解析器必须用服务端ExecutionSecurityContext.source_task_id和持久同user/round父子关系交叉核实父来源。关联必须唯一，对应child/step/plan版本与子记录一致；父为真实受控cross.start_task、原请求号与原话完整。缺失/foreign/异绑定/读取失败继续RiskFactsUnavailable，不以marker或空话代替。参数仍由原operation/revision/ref精确验证。

父原话及同任务跨会话的父/子受控文本跟进是风险数据，不是确认、验证、权限或会话迁移。普通有UUID的Harness文本续做在现有归属、非终态与权限检查后写入已有RiskConversation，同原请求去重；不存专用details原文或从模型/普通memory/HTTP显示文字猜来源。解析器仅向检测器传原文，公开引用仍为hash。

局部用真实平台/安全/银行检查：危险父原话和后续危险提示不丢；正常来源准确；错误关联、step/plan不符、foreign、缺原话/原请求拒绝；重启/跨会话历史仍保留。没有风险profile新增或检测语法白名单，不把unknown改safe；P01具体演示profile另待本人裁定。
