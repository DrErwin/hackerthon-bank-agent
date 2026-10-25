# 05：生日编辑候选检查点的一次封存

Ticket ID: v05-birthday-platform-dependencies/05
Package: [v05-cross-linkage/packages/01-platform-bank：公共接缝与模拟银行](../../v05-cross-linkage/packages/01-platform-bank.md)
Spec: [G3对账与发布条件](../g3-reconciliation.md)
Type: 开发（本轮只读核查与规划）
Owner: Erwin（v0.5统一负责）
Directory: `backend/app/storage/`
Status: planned / blocked — 未授权实施；原四票同样不实施。
Implementation assignee / accepted at: 未领取。
Blocked by: 中控明确实施授权；与[本组03：受控编辑交接](03-platform-edit-handoff.md)及[v05-cross-business/08：生日商品数量与未执行部分调整](../../v05-cross-business/issues/08-birthday-quantity-and-unexecuted-revision.md)在设计层确认候选ref/绑定/首次胜者语义；不依赖对方代码先完成，不形成实现循环。
Core scenarios: P12—P15；原Q03/Q06及XL-B05/X08，定义见[规格框架](../spec.md#6-testing-decisions只设计未运行)。

## 实际缺口（源码推演，未运行）

SqliteCheckpointSaver已有namespace/精确ID读取，但checkpoint_blobs按(thread,namespace,channel,version)可INSERT OR REPLACE。
当前put没有封存候选、没有“同一edit/source/ref首份内容胜出”的接口；新方法保护但旧put/put_writes可覆盖也不合格。
因此不把新checkpoint UUID或task CAS单独当隔离；不重做已有精确读取。

## 最小输入输出候选

输入为受控task/thread内的后台预留候选完整ref、edit/source/请求摘要绑定、待写checkpoint与元数据；不是客户端来源。
输出为首次封存的精确ref与可回读的完整胜者，或绑定冲突。相同绑定的竞争/重试读首次内容和新input ID，不能覆盖后再比较。
实现可复用现有事务、唯一约束及必要最小持久元数据；不预定新表/迁移号，不建立通用工作流框架。

## Acceptance criteria

- [ ] 候选与源/其他候选namespace隔离；只改变checkpoint ID但共用通道version不能算隔离。
- [ ] 候选ref预先绑定，先验证再写；单胜者持久、重开可读，异参冲突不改变已有blob/checkpoint。
- [ ] 封存后的原put/put_writes等覆盖路径均拒绝；不能只约束新方法或依赖进程内锁。
- [ ] 多步SQL全部在既有事务内，失败完整回滚；完整ref的归属/thread校验保留。
- [ ] 旧namespace/普通LangGraph与单件流程兼容；不迁移共享库、不清理历史孤立状态来凑验收。
- [ ] 不负责选可编辑项/安全策略或任务发布；03用既有task CAS同次发布ref/result/完成投影，Cross08消费胜者。
- [ ] 对现有存储不足给出具体反例与最小变化，不在本票修改memory/platform/cross/security或公共契约。

## Verification / downstream

实施后在隔离临时库验证共享version覆盖、同edit并发/重开、重复/冲突、旧put绕过、写中失败及原保存器回归。
本轮无测试/模型/CI运行，不声称这些条件已验证。03依赖本票真实交付；G1/G2本人决定及G3消费签名仍另行取得。
