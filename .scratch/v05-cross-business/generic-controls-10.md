# 票10：联动父计划的通用任务操作

## 问题与边界

真实模型已正确路由减少开销，退订子任务已完成；API F11 发送 `choice=resume`，Cross 却只把空 response 当续做，把 `resume` 作为菜单 ID 拒绝，父任务 HTTP 503。F13 发送 `query=True`，也需检查消费边界。

- 只消费现有通用任务控制，不增加端点、工具、授权或银行规则。API 目录不改。
- 继续可刷新父计划的真实子任务结果，子任务仍待确认/验证时保持原等待，不替用户批准。
- 查询只沿原子任务/原操作观察，不派发新写动作，不将未知当成功；没有已提交未知动作时不得以 query 跳过菜单。
- 当前菜单、旧 interaction/option、取消及终态仍保持既有约束，不让裸通用控制冒作菜单选择。
- 养老金和生日的现有敏感恢复 SOP 不受通用控制绕过；会话恢复09独立交付。

## 证据要求

先用原失败库的只读 SQLite 备份复现，再在新建隔离数据上通过真实 ASGI HTTP 固定回归；模型规划器显式拒绝任何意外调用。核对原退订 operation 仍仅一次，原失败资料保持。

## 已取得的反馈

- 基线 `695ce6e5`：原中控复现脚本改用 `mode=ro` 打开源 SQLite 并只在新备份发 HTTP，强制禁止 planner；7.4 秒重现父 resume 503。
- 新增本目录 ASGI HTTP 回归，在已由服务器确定 Cross 提案的隔离任务上开始，全程不调用模型：修复前 5 failed / 1 passed，30.45s；[原始 JUnit 无损归档](evidence/2026-10-27-controls-10-before.xml.gz)。不把这个预置提案测试作为新的真实模型路由证据。
- 最小修复后 6 passed / 30.03s：[定向 JUnit](evidence/2026-10-27-controls-10-after.xml)。覆盖子成功后父继续、子待确认、expense/pension 菜单保持、旧菜单拒绝/取消/终态查询、真实提交后丢响应的未知原号查询；最后一例 bank write 调用始终一次。
- 原失败场景再取只读备份：HTTP 200、父状态 waiting_input、原退订操作仍仅一条 succeeded、模型调用0；[最小回放摘要](evidence/2026-10-27-controls-10-captured-green.json)。原失败批次和原库不改写，未重新调用真实模型。
- F13 核查结论：活动普通父卡只发布 resume/cancel，因此 query-result 仍409；终态 query 由 Cross.resume 的终态分支返回原结果。没有把 query 当 _advance 或开放新写动作。

完整 Cross 目录回归与最新 main 同步后补证；独立两轴/CI/真实页面验收分别由中控记录。
