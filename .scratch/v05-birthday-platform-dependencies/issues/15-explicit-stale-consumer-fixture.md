# v05-birthday-platform-dependencies/15：将旧卡消费者明确为提供方测试夹具

Ticket ID: v05-birthday-platform-dependencies/15
Package: v05-cross-linkage/packages/01-platform-bank
Type: 开发（仅测试维护）
Owner: Erwin；执行 root AI
Directory: `backend/app/agent_platform/`
Status: ready_for_review — 既有提供方28项通过，待独立两轴及Cross09组合
Accepted by: 本对话 AI，依据用户完成非比赛资料任务授权及 Cross09 联调发现
Accepted at: 2026-10-27
Depends on: PR #335；Cross09 合入前的组合前置

## 问题与最小验收

335 的提供方回归依赖真实 Cross 尚未消费新会话投影、因而返回旧卡的历史前提。Cross09 将修好这个前提；提供方仍须独立证明旧卡、重复确认ID及参数/来源漂移不能得到权限。

- 普通提供方用例显式注入返回平台原公开结果的 faulty consumer，保持原拒绝与所有资金/CAS/历史断言。
- 先建立新确认、再返回旧卡的专门反例保留独立注入，不得被普通夹具覆盖或删除新检查。
- 不改 Cross 或平台生产代码，不读取 Cross 私有状态，不新增放行、改期望或重写335历史证据。
- 运行既有提供方文件验证夹具本身，随后在 Cross09 组合中验证真实消费者与 provider 守卫各自成立；独立双轴后单独 PR。

## 验证

基线main `f4a98724`（含335），生产代码未改。原提供方文件 **28 passed / 0 failed，94.43秒**；[原始JUnit](../evidence/2026-10-27-platform15-fixture.xml)，SHA256 `e680321957560a6388907d6408b0a1ec79e57cc50c921eacf15c4e1f4bce15f1`。

只把历史消费者前提换成显式不合格消费者；原6敏感阶段、来源、CAS、真实退役、原号观察和复用确认ID拒绝的全部断言保持。专门的新check后返回旧卡用例自行注入并直接调用Harness，不会被普通夹具覆盖。没有模型或银行共享库操作；不把本28项当Cross09真实消费已通过。
