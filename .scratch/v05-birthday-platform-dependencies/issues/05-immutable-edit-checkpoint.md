# 05：生日编辑候选检查点的一次封存

Ticket ID: v05-birthday-platform-dependencies/05
Package: [v05-cross-linkage/packages/01-platform-bank：公共接缝与模拟银行](../../v05-cross-linkage/packages/01-platform-bank.md)
Spec: [G3对账与发布条件](../g3-reconciliation.md)
Type: 开发（本轮只读核查与规划）
Owner: Erwin（v0.5统一负责）
Directory: `backend/app/storage/`
Status: done — 2026-10-26 实施、两轴独立审查闭合（规范轴 PASS / 规格轴 PASS，v7 只加表由中控确认），PR #307 squash 合入 `5863340`；真实 E2E 与验收未由本票完成。
Implementation assignee: Erwin 授权执行对话（本对话，AI 代理）；accepted at 2026-10-26。
领取与顺序见[生日系列执行记录](../../v05-control/birthday-series-2026-10-26.md)。
Blocked by: 中控明确实施授权；与[本组03：受控编辑交接](03-platform-edit-handoff.md)及[v05-cross-business/08：生日商品数量与未执行部分调整](../../v05-cross-business/issues/08-birthday-quantity-and-unexecuted-revision.md)在设计层确认候选ref/绑定/首次胜者语义；不依赖对方代码先完成，不形成实现循环。
Core scenarios: P12—P17；原Q03/Q06及XL-B05/X08，定义见[规格框架](../spec.md#6-testing-decisions只设计未运行)。

## 实际缺口（源码推演，未运行）

SqliteCheckpointSaver已有namespace/精确ID读取，但checkpoint_blobs按(thread,namespace,channel,version)可INSERT OR REPLACE。
当前put没有封存候选、没有“同一edit/source/ref首份内容胜出”的接口；新方法保护但旧put/put_writes可覆盖也不合格。
因此不把新checkpoint UUID或task CAS单独当隔离；不重做已有精确读取。

## 最小输入输出候选

输入为受控task/thread内03已持久预留的候选完整ref、接受版本、原task/start请求或普通请求/原运行事件的转换关联、来源条件/摘要、待写完整checkpoint及必要元数据/关联写；不是客户端来源。真实编辑另带原edit_ref/安全事实关联。
新任务初始根没有edit_ref/source：只在后台核验首次初始化且无任何已发布Cross状态、匹配03原start预留时允许无前驱；不得将普通缺源、旧任务缺ID当新根。普通输入/事实/异常后继无edit_ref，但必须绑定上次不可变已发布完整source_ref；编辑的edit_ref仍必有。这些是同一窄保存能力的受控输入条件，不新增公共协议或泛化状态引擎，详见[三类来源及发布](../g3-reconciliation.md#没有编辑请求的初始与普通状态)。
输出为首次封存的精确ref与可回读的完整胜者（状态/结果及必要元数据/关联），或绑定冲突。相同原转换/源/摘要的竞争与重试读取首次内容和原新input ID；不同绑定冲突不改旧内容，不能覆盖后再比较。根重试仍沿03已保存的原start关联，不用新run_id补造一次初始化。
实现可复用现有事务、唯一约束及必要最小持久元数据；不预定新表/迁移号，不建立通用工作流框架。

## Acceptance criteria

- [ ] 候选与源/其他候选namespace隔离；只改变checkpoint ID但共用通道version不能算隔离。
- [ ] 候选ref预先绑定，先验证再写；单胜者持久、重开可读，异参冲突不改变已有blob/checkpoint。
- [ ] 初始根、普通输入/事实/异常后继与编辑候选同等封存；无edit不等于可以绕过保护，无source仅限已验证初始根。03/08不能只封编辑candidate、却让后续读取普通source时回到可覆盖blob。
- [ ] 完整回读值、元数据及必要关联写封存后，原put/put_writes等覆盖路径均拒绝，发布后仍受保护；后续状态另用隔离namespace。不能只约束新方法或依赖进程内锁。
- [ ] 多步SQL全部在既有事务内，失败完整回滚；完整ref的归属/thread校验保留。
- [ ] 旧namespace/普通LangGraph与单件流程兼容；不迁移共享库、不清理历史孤立状态来凑验收。
- [ ] 不负责选可编辑项/安全策略或任务发布；03用既有task CAS同次发布ref/result/完成投影，Cross08消费胜者。
- [ ] 对现有存储不足给出具体反例与最小变化，不在本票修改memory/platform/cross/security或公共契约。

## Verification / downstream

未来定向验证设计：隔离临时库检查共享version覆盖、同edit并发/重开、重复/冲突、旧put绕过、写中失败及原保存器回归；P16/P17再检查无edit/source根封存与原start重试、普通输入/事实/异常后继的完整source保护、普通缺源拒绝冒充根。源/根候选封存后仍未由03发布时，不能用它宣称活动状态已生效。

## Delivery record（2026-10-26 本对话实施）

- 实现：`backend/app/storage/checkpoints.py`（封存接口与 `put`/`put_writes`/`delete_thread` 拒绝）、
  `backend/app/storage/application.py`（应用库 v7 只加 `checkpoint_seals` 表与索引，不回填）、
  `backend/app/storage/README.md`；测试 `backend/app/storage/test_immutable_checkpoint.py`（12 例）。
  提交/PR：`codex/v05-birthday-immutable-checkpoint`，[PR #307](https://github.com/DrErwin/hackerthon-bank-agent/pull/307)。
- 定向验证：`python -m pytest app/storage -q` → **69 passed**；调用方 `app/agent_platform/test_harness.py`
  `app/modules/cross/test_cross_birthday.py` → **57 passed**；另 `app/modules/bills app/modules/subscription app/memory`
  → **495 passed**（实施者报告，已由本对话在 rebase 后重跑 `app/storage` 复核 69 passed）。未跑全量后端/真实模型/CI。
- 双轴独立子代理审查（AI，非本人/Ringo 签核）：**规范轴 PASS**（必须修 1：README 把「跨进程竞争」写成已由自动测试覆盖，
  实际只测同进程多线程——已改为如实措辞并注明双进程探针复核非固化为测试）；**规格轴 PASS**（8 条 AC 全满足；
  必须修 2 项为记录类：本记录 + v7 新表获批，见下）。
- **中控确认（本对话，Erwin 授权）**：新增最小表 `checkpoint_seals` 与应用库 v7 属票面允许的「必要最小持久元数据」——
  现有表无法承载 (thread, namespace)/(thread, binding_digest) 唯一绑定，且必须与检查点写同事务；
  只加表+索引、不回填、不迁移共享库、不清理历史。旧代码拒绝 v7 库属既有既定行为（新隔离数据目录使用）。
- 如实边界：05 不能独立证明 source 已由 03 发布、不能核验 root 的「03 原 start 预留」语义（归 03 CAS 与 08 消费）；
  旧任务未封存历史不能当 source，G3 旧任务编辑仍按对账稿 blocked；只提供同步封存接口，未加 async 孪生（03 现为同步调用）。
- 真实 E2E、200%/读屏、页面与安全接受未由本票完成。
