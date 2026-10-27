# 平台23：当前冻结原号的只读提交观察

Status: implemented_pending_review
Owner: Erwin（v0.5）；执行 frontend_acceptance 子代理，顺序承担平台目录
Accepted by: Erwin，通过本轮非资料任务授权及中控明确分派
Accepted at: 2026-10-27
Package: [v05-cross-linkage/packages/01-platform-bank](../v05-cross-linkage/packages/01-platform-bank.md)
Directory: backend/app/agent_platform/
Source issue: [Issue #352](https://github.com/DrErwin/hackerthon-bank-agent/issues/352)，转给 Erwin / Assignee DrErwin

## 问题与固定接口

Cross09 原红 `14117e642e10678d0fe6311e861868004d248512` 真实链：专用预算采用→S2 fresh新确认和验证码/模拟人脸→新冻结已完成→Cross完成快照发布前中断。取消只看到旧验证快照而误称取消，银行仍冻结500元且hold关闭。原红不在本票重写；Cross Protocol和消费由09作者另改。

新增只读 `BirthdayTaskPorts.observe_freeze_submission(context, plan, operation_id: str) -> str`，返回 `not_submitted` / `submitted` / `unknown`。调用者须位于既有 Harness 任务串行锁内；这是观察，不是关闭hold或动钱的授权。

- FO01：先走当前 owned task 的现有user/round/session门；只认当前 `birthday_actions.freeze` 的准确op、正整数revision及与plan相同的冻结参数。历史退休号或无绑定为unknown，不改旧session绕读。
- FO02：仅原号银行Found且终态（succeeded/failed）才能submitted，必须匹配bank.freeze_funds及准确op。completed claim不能替代银行事实。
- FO03：not_submitted须无claim、真实OperationNotFound、公开gateway在途已排空，再读claim仍无；并复核当前动作没变化。尚在途绝不报没提交。
- FO04：processing/unknown/completed claim但银行未找到、银行processing、来源/安全/银行读取失败或其他不确定均unknown。None不当未提交。
- FO05：探针不调用gate、execute、requery、grant、bind、retire，不新建claim或银行效果，不修改原确认/验证和授权。

## 局部验证与边界

新测试使用现有NoopModel/Harness/安全/MockBank组合与隔离临时库：未提交、真实成功、真实响应丢失、各claim状态、读取失败、错owner/round/session/task/op/action/revision/plan、退休旧号、真实在途及读取间claim出现；比较原状态，拦住探针内写入。

先保存缺少公开能力的真实局部红，再实现同一接缝转绿；旧运行装配定向回归另记。仅agent_platform和本组票据，不改Cross/security/services或私密配置，不跑真实模型或共享失败库。跨目录取消释放500和未知保hold由Cross09依赖本票合入后验证；局部不冒称最终全backend、页面或真人安全接受。

原始本地过程：缺少方法的1 failed/7.98s；第一版16项中15过/1失败（错轮STALE_ROUND被误吞，已修并保留原XML）；随后28项全过/53.95s。补银行None/异常和读取间动作漂移后，基于main ef8f9220的完整局部组合为31个新探针+5个旧装配，共36 passed/76.92s。各批重叠，不加总为更多唯一用例；最新主线组合另记。
