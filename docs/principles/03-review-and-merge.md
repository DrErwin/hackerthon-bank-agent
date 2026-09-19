# 代码 Review 与合并原则

适用对象：Erwin（架构、底座、最终合入），以及所有提交 PR 的人。

**当前状态：仓库已在本地初始化（`main` 分支），GitHub 远端待建立。** 远端建立后 `main` 转为受保护分支：禁止直推，唯一合入路径是 PR。远端建立步骤与提交信息格式见 [Git 与提交约定](../agents/git-workflow.md)。

> 目录基线见 [系统框架 v0.5](../architecture/system-framework-v0.5.md) §9 的 `backend/app/` 建议结构。
> 银行接入层、模拟银行、前端的目录名与 owner 尚未在契约冻结前定死，见 §5 的占位说明。

## 1. 仓库与分支总则

- 全员同一个仓库（现为本地 `main`，GitHub 远端建立后改为同一远端），`main` 始终可运行已合入模块的测试。
- 合入方式团队统一为 squash merge（主线每个 PR 一条记录）。
- 作者在合入前保持 `rebase origin/main`。冲突由作者解决，不在 `main` 上手工拼接。
- 推送已 rebase 的功能分支使用 `git push --force-with-lease`，禁止无 lease 强推。
- 合入后删除远程功能分支；本地 worktree 重置到最新 `main` 或移除。
- 新手 / 非代码成员 git 卡住时由 Erwin 代操作，不要求独自完成 rebase / force。

> 注意：squash merge 会重写提交历史，与「从功能分支拉出的依赖分支（Depends on #编号）」组合时，
> 依赖关系只能靠 PR 编号维护。堆叠分支的 rebase 比普通分支更容易出错，统一由 Erwin 协助处理。

## 2. 合入顺序（按依赖，不按提交先后）

1. 公共契约 `contracts/`
2. Agent 底座、银行接入层、模拟银行接缝
3. 安全执行器与策略
4. 单业务模块的公开入口与测试
5. 模块内部流程与私有工具
6. 跨场景联动
7. 前端展示与适老化

底座与安全 PR 和业务 PR 同时出现时，先合底座 / 安全。联动 PR 不得早于其依赖的公开能力。

## 3. Erwin 写代码时的原则

- 先交团队能用的基础设施：契约、模块模板、假银行接入、最小执行器、CI。
- 自己的改动同样走小 PR，不攒「架构大补丁」卡住所有业务线。
- 不替业务写场景 SOP，除非对方明确卡死且已沟通由你顶上。
- 契约是唯一公共来源。改契约必须写兼容说明：字段新增可以，删除或改义必须通知全员并给迁移窗口。
- 银行规则只存在模拟银行内；接入层只做协议隔离，不塞业务 if-else。
- 公共文件与业务文件不要混在同一个 PR。

## 4. Review 必看清单

通用：

- 目录有没有越界。
- PR 是否只做一件事，测试是否与声明一致。
- 是否从过期分支开出，是否需要先 rebase。
- 有依赖是否标明 `Depends on #n`。

业务 PR 额外看：

- 是否引用公共契约而非复制。
- 是否直连银行或复制银行规则。
- 敏感操作是否有确认回环。
- 联动是否只调用公开能力。

安全 / 底座 PR 额外看：

- 默认拒绝是否被放宽。
- 执行器是否仍覆盖私有工具与局部 Agent。
- 审计是否可回放本次变更，查看入口是否只读。
- CI 与模块注册门槛是否仍能拦住未声明工具。

## 5. 谁必须批准（CODEOWNERS 规则）

CODEOWNERS 只认 GitHub 账号（`@username`）或团队（`@org/team`），**不支持中文昵称**。
GitHub 远端建立前先收集 5 人真实用户名替换下面的占位账号（见
[Git 与提交约定](../agents/git-workflow.md#3-远端建立后的动作)）：

```
backend/app/contracts/         @erwin
backend/app/agent_platform/    @erwin
backend/app/api/               @erwin
backend/app/security/          @ringo @erwin
backend/app/memory/            @ringo @erwin
backend/app/modules/transfer/  @liangshuang
backend/app/modules/bills/     @liushui
backend/app/modules/cross/     @zhouenyu
```

待契约冻结补齐（目录名未定，不写入 CODEOWNERS）：

- 银行接入层 / 模拟银行目录：owner 建议 = Erwin（银行基建），目录名待定。
- 前端目录：owner 待定（见 [项目跟踪](../01-项目跟踪.md)「适老化负责人待指定」）。

业务负责人可以批本模块逻辑。Erwin 批边界、契约兼容和「能否进 main」。安全相关 ringo 未批不得合。
三个业务模块目录名（transfer / bills / cross）在契约冻结时一并定死，改名须同步更新 CODEOWNERS。

## 6. 合并窗口与沟通

- 每天固定 1～2 次合入窗口，窗口外只 review、不合破坏性变更。
- 契约或安全策略合入前，在群里预告，合入后通知全员 rebase。
- 打回时写明原因和下一步：越界 / 缺测试 / 缺声明 / 需拆 PR / 需等依赖。
- 不把「谁先提交谁不用 rebase」当成奖励。后到的人 rebase，先到的人也不许在 main 上抢写。

## 7. 冲突处理

- 只碰业务自有目录：作者自行解决。
- 公共文件冲突：停合，由该文件 owner 决定保留哪边，必要时抽成扩展点后再合。
- 两个业务同时改底座同一处：退回双方，先合接口设计，再各自实现插件。
- 禁止为赶进度在 main 上直接编辑冲突文件后推送。

## 8. 合入后的责任

- 合并人确认 CI 绿、依赖 PR 已合、CODEOWNERS 已批。
- 合入后冒烟失败：先回滚或立即热修，不继续往 main 堆新功能。
- 每个合入的能力应能在模块测试中独立复现；没有测试的回归不算修完。
