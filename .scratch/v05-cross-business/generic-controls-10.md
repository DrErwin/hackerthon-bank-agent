# 票10：联动父计划的通用任务操作

## 问题与边界

真实模型已正确路由减少开销，退订子任务已完成；API F11 发送 `choice=resume`，Cross 却只把空 response 当续做，把 `resume` 作为菜单 ID 拒绝，父任务 HTTP 503。F13 发送 `query=True`，也需检查消费边界。

- 只消费现有通用任务控制，不增加端点、工具、授权或银行规则。API 目录不改。
- 继续可刷新父计划的真实子任务结果，子任务仍待确认/验证时保持原等待，不替用户批准。
- 查询只沿原子任务/原操作观察，不派发新写动作，不将未知当成功；没有已提交未知动作时不得以 query 跳过菜单。
- 当前菜单、旧 interaction/option、取消及终态仍保持既有约束，不让裸通用控制冒作菜单选择。
- 养老金和生日的现有敏感恢复 SOP 不受通用控制绕过；会话恢复09独立交付。
- 父计划已有持久停止原因时，通用继续只核实原子任务并收尾；首笔未知稍后核实成功不能创建后续转账任务。未知期间保持资金安排，核实完成后显示部分完成/后续停止并解除安排（PRD §4.2）。

## 证据要求

先用原失败库的只读 SQLite 备份复现，再在新建隔离数据上通过真实 ASGI HTTP 固定回归；模型规划器显式拒绝任何意外调用。核对原退订 operation 仍仅一次，原失败资料保持。

## 已取得的反馈

- 基线 `695ce6e5`：原中控复现脚本改用 `mode=ro` 打开源 SQLite 并只在新备份发 HTTP，强制禁止 planner；7.4 秒重现父 resume 503。
- 新增本目录 ASGI HTTP 回归，在已由服务器确定 Cross 提案的隔离任务上开始，全程不调用模型：修复前 5 failed / 1 passed，30.45s；[原始 JUnit 无损归档](evidence/2026-10-27-controls-10-before.xml.gz)。不把这个预置提案测试作为新的真实模型路由证据。
- 最小修复后 6 passed / 30.03s：[定向 JUnit](evidence/2026-10-27-controls-10-after.xml)。覆盖子成功后父继续、子待确认、expense/pension 菜单保持、旧菜单拒绝/取消/终态查询、真实提交后丢响应的未知原号查询；最后一例 bank write 调用始终一次。
- 原失败场景再取只读备份：HTTP 200、父状态 waiting_input、原退订操作仍仅一条 succeeded、模型调用0；[最小回放摘要](evidence/2026-10-27-controls-10-captured-green.json)。原失败批次和原库不改写，未重新调用真实模型。
- F13 核查结论：活动普通父卡只发布 resume/cancel，因此 query-result 仍409；终态 query 由 Cross.resume 的终态分支返回原结果。没有把 query 当 _advance 或开放新写动作。

## 最新主线组合验证

只重放本票到 main `e4f0fe50`（已含 API #327 和安全 #330）。先前本地基线的 API 五个提交已压缩合入，未再次携入本 PR；本票 range-diff 为 `=`。`695ce6e5` 与该 main 的 API 树均为 `9977e0613db524d0fbdaa201c36bb4c3c8b55732`，没有手改 API 冲突。

受测提交 `b1f11f93`，Cross 树 `8e8ce8ba2c5cb33bbe87415ead7d28bf2022e474`。命令：`python -m pytest backend/app/modules/cross -q`，独立临时目录，结果 **126 passed，256.99s，exit 0**，包含上述六个 HTTP 节点与既有养老金/生日/预算/撤离业务回归。[原始 JUnit](evidence/2026-10-27-controls-10-main.xml)。后续只补证据，Cross 源码树保持；独立两轴/CI/真实页面验收分别由中控记录。

本票没有运行新真实模型或页面；原模型路由成功/子任务成功及失败 HTTP 批次由中控原资料保留。没有修改风险配置、共享演示库、API、平台或安全目录，也没有实现09会话恢复。

## Spec P2：叫停后只核实收尾

原通用继续分支在父计划已有 `stop_reason=user_cancelled` 时仍调用养老金推进；首笔未知查明成功后，竟创建第二笔前置账户查询与转账确认子任务。PRD §4.2要求叫停后停止新敏感动作，保留已成功事实，只核实原操作并收尾。补修只在该generic非生日、已允许resume的分支增加两行：有持久停止原因则复用现有 `_closeout`，不走 `_advance`；query与生日SOP保持原路径。

新增真实ASGI HTTP回归 `test_stopped_pension_parent_closes_after_unknown_transfer_is_verified`：逐项采用500元与600元两笔计划，第一笔完成正式确认/验证码并真实提交模拟银行；在网关边界丢弃提交响应、暂使原操作回查超时，父叫停后保持未知与原资金安排。恢复回查后只查原子任务/原operation，再F11收尾，核对child ID全集不增加、部分完成且后续停止、保留 `user_cancelled`、账户安排解除、实际提交调用一次。

此新增回归显式将本次隔离runtime的公开risk assessor设为固定LOW，以隔离Cross状态机；仍使用真实HTTP、Harness、Cross、确认/验证码、模拟银行和原号查询，不修改生产策略或私密演示配置。正式local_demo最初在首笔前合法暂停，另有测试前置与诊断调整；六份此类失败报告已[无损归档](evidence/2026-10-27-controls-10-stop-setup.tar.gz)，不算目标红例或生产缺陷。它们不替代原6HTTP或任何真实模型安全证据。

- 目标红例：未补修入口（`6a7d309d`加新增回归），**1 failed /22.59s/exit1**，失败在原号核实后F11新增2个child ID；[原始JUnit无损gzip](evidence/2026-10-27-controls-10-stop-before.xml.gz)，解压SHA256 `F17CE74C8F4E093DDA44DEB56833312C0B2A6F2E05DD7E8FE33BAA0F97C33E7A`。
- 最小修复后同一目标回归：**1 passed /19.60s/exit0**；[原始JUnit](evidence/2026-10-27-controls-10-stop-after.xml)。
- 只运行一次最终完整Cross目录：基线 `main@dcbf6144669eabd29cb5468881bf816e88aafc95` 已含API329（`87e30a94`祖先核验退出0），只重放原本票两提交（range-diff均`=`）及补修。受测提交 `481d811841523ef05e794d66b8aa0bbeccc4bed0`，Cross树 `07da2410552da64ca46a2454aa931fcd61e1df03`；**127 passed /0 failed/0 error/0 skipped，164.26s，exit0**，其中本文件7个HTTP用例（原6+新1），JUnit127个用例且唯一127、无重复。命令 `python -m pytest backend/app/modules/cross -q --tb=short --junitxml=.scratch/v05-cross-business/evidence/2026-10-27-controls-10-stop-main.xml -o junit_family=legacy`，运行期间源码冻结；[原始JUnit](evidence/2026-10-27-controls-10-stop-main.xml) SHA256 `C5AFEBBDFB7334292FA4C24113F5AEF2CD34188DACF18C319E9F1B91EF421C3D`。

原126项、原失败JUnit与只读回放摘要四份资料同原head `a473a985` 的blob逐项相等（`git diff --quiet`退出0），没有覆盖或重命名。此次是含API329的新主线依赖上的Cross组合工程验证，不是全API重跑或实际模型/页面验收。养老金前置菜单的账单对比状态文案另归后继Cross11；本332不混入。

证据保存时main已前进至前端PR331合入的 `091032fa2354a5b09b94b75465b28289b82be1d3`，本票四提交随后无冲突机械rebase。新旧基线backend差异为空；交付backend树 `527c11fd6636c442d8f1a531cf5ed9665346b1cc` 与受测 `481d8118` 完全一致，Cross树仍 `07da2410552da64ca46a2454aa931fcd61e1df03`，`git diff --quiet 481d8118 HEAD -- backend`与main祖先核验均退出0；未因前端机械变基重复回归。
