# 22：API续办保留可信子任务父关联

Owner: Erwin；root按完成非比赛资料任务授权实施。仅 `backend/app/api/`。

21真实P01集成发现：首次子转账由Harness正确带parent，HTTP确认/验证重新建立TrustedContext却固定parent_task_id=None，19因此拒绝风险来源，银行0写。22只从已认证同user/round的公开ApplicationStore持久parent关联填回parent_task_id，已有API thread/task/session门及19关系/step/plan核验不放宽，不从请求体或模型推断，不改风险阈值/授权。

局部以真实API/Harness/安全/MockBank已有A2场景验证子确认、验证、原号结果/恢复仍用持久父关系；普通根任务仍None，foreign/session/round原门拒绝。规划器是明示脚本替身，父子dispatch由测试服务端调用，不冒称完整P01；完整两笔由21在22合后按原断言验证，root后继实际模型另开新批。
