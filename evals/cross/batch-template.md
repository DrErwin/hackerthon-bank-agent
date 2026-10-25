# 运行批次模板（未运行，不是结果）

实际运行后按 [runbook](runbook.md) 归档 JSON gzip、同名人读摘要、manifest 和截图。本模板不预填成功。每个案例/变体一份记录，批次可包含多条；字段是评测证据，不是新增公共 API 契约。

## 批次头

- batch_id / 开始结束时间（含时区）/ executor / 完整票号 / 原设计编号 / variant_id
- git commit / worktree / 合入依赖 commit / 前后端进程与端口 / 浏览器设备版本
- 模型真实入口类型（普通或 Coding Plan）、model_name、配置版本（不含密钥）
- 独立数据库目录、种子版本/哈希、业务时钟/期间、demo_round_id、虚构用户
- status：未运行 / 通过 / 失败 / 阻塞；blocking_provider / 完整依赖票或待中控关联的缺口
- 前序失败批次、修复 commit / PR、复验范围；原失败文件保留

## 案例记录

- 原始自然表达（仅虚构且已脱敏）、变体步骤；基线事实、预期断言/数值/状态，运行前填写
- page_steps：输入/选择/方案采用/每项确认/验证/取消/刷新/重启，截图附件与时间
- model_records：脱敏真实请求/响应及工具选择/失败编号，trace关联；缺失写blocked
- http_records：时间、方法、路由、状态码、request_id、task_id、响应脱敏摘要；不含Cookie或验证码
- task_links：thread_id、parent_task_id、child_task_id、step_id、interaction_id、confirmation_id/version、verification_id（仅引用）、action_revision
- operations：operation_id、action、受控parameters_ref、订单/冻结/核销/释放关联、原操作查询记录
- before / after：银行/签约/流水/订单/冻结受控查询证据及可复算金额；不能只写助手回复
- counters：按动作及operation_id分别记录工具请求尝试数、银行写请求数、已提交操作数、实际结算效果数；列确认前、提交后、恢复后的差值
- fault：指定故障类型/动作/触发方式/作用范围/回查事实；没有入口就blocked，不假装注入成功
- assertions：expected、actual、pass/fail/blocked、evidence_ref；unknown 不填 success
- result：各步骤已办/未办/未知/部分成功、停止原因、下一步、资金收尾；核对卡片、聊天和总回执

## 分层结论

| 证据层 | 结论及引用（各自填写） |
|---|---|
| 文档/运行准备 | 未运行 / 通过 / 失败 / 阻塞 |
| 离线或模块测试 | 同上；与真实调用分开 |
| 真实模型 | 同上；含提供商故障，不以固定输出替代 |
| 真实HTTP | 同上；进程/路由与记录 |
| 页面→模型→HTTP→银行/生活服务 E2E | 同上；任一必要层缺证据不能填通过 |
| 200% / 键盘 / 读屏 / 真机软键盘 | 各自结论、设备、步骤、证据或阻塞 |
| AI规范/规格审查 | 实际审查代理/基线/结论，不是人签核 |
| 银行专项 / 安全专项 | 报告/范围/缺口，不自动继承别场景结论 |
| PM体验接受 / 例外 / Ringo本人签核 | 分别记实际人、日期、范围；没有就未记录 |

manifest 每个报告条目包含 batch_id、原场景/变体列表、状态计数、断言计数、json.gz/摘要/附件路径及解压JSON的sha256。提交前人工检查脱敏与关联完整性，不提交数据库、秘密配置或原始HAR。
