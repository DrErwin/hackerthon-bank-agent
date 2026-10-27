# 票09：生日会话恢复的安全提供需求

## 2026-10-27 续作范围与消费规格

中控在平台 PR #335 合入 `30cbe740` 后明确激活本票生产消费。仅修改
`backend/app/modules/cross/` 及本组票据；保留已合 PR #332/#334 的通用继续、
叫停和来源说明。下面原始探针与原始 gzip 证据继续保留，不改成已通过。

依赖：安全 PR #330 在同一事务核实未提交与真实银行旧挑战退休；平台 PR #335
先封存原发布来源，在任何新会话安全检查前退休旧 attempt，再唯一关联新 attempt。
Cross 只消费公开 `BirthdayPorts.session_recovery_status(context)`：
`status` 为 `fresh` 或 `observe`，带 `original_operation_id`、`action_name`、
`action_revision` 与可空的 `replacement_operation_id`。不读平台私有恢复记录，
不改确认、挑战、授权、claim 或历史操作。

- R09-1：冻结、下单、核销的确认/验证共六个敏感等待点，`fresh` 与本模块
  原 pending 的 target/原号一致后清理旧等待，只重走相同稳定执行项的公开检查。
  必须得到目标会话的新确认，批准后才有新验证，真实银行链可继续；已发生事实保留。
- R09-2：`observe` 清除旧卡和旧验证入口，保留原号并只核实原冻结、订单、付款。
  恢复及查询不自动推进购买或释放；明确停止才进入原限定收尾。未知不能当未提交。
- R09-3：同目标会话的重试、重新构建运行时与迟到旧确认/挑战不能复用旧授权、
  重复写入或串接旧菜单。新卡的受控修改仍走原 G2；取消仍走原限定收尾。
- R09-4：已 claim/unknown、已冻结/已付款事实不轮换操作、不重冻、不重复订单/核销、
  不退款。缺投影或不匹配明确拒绝恢复，不能把当前缓存卡当新卡。

测试接缝由中控任务明确指定：真实 Harness 的 recover_session/resume、公开确认/验证、
BirthdayPorts 与模拟银行结果；规划器仅为明示测试替身。先保存六阶段消费失败，再最小修复，
追加执行/未知、断点、重启、晚回调与编辑/取消分支，最后跑 Cross 全目录。此层不替代
真实模型、HTTP 页面走查或真人安全接受。

### 续作中间结果与明确依赖

- 平台 #335 已就绪但 Cross 未修时，新六阶段真实组合 **6 failed / 21.51s**，
  均为旧卡被 provider 拒绝；[原 JUnit 无损归档](evidence/2026-10-27-session-recovery-09-provider-ready-red.xml.gz)。
- 最小 fresh 重查后，六阶段均能生成新会话/新操作的确认且随后真实确认、验证、
  冻结/下单/核销成功；完整收尾断言 **2 passed / 4 failed / 44.37s**。
  [原 JUnit](evidence/2026-10-27-session-recovery-09-before-release-provider.xml.gz)保留：
  已在 S1 冻结的四个 order/capture 恢复阶段，平台 release_snapshot_writer 用 S2
  读取原 S1 确认失败，审计 source=None，最终 `AUDIT_UNAVAILABLE/audit-before-release`。
  中控另接平台票16；本票不扮作 S1、不削减最终 SUCCEEDED 断言。
- observe 初始真实已执行三分支 **3 failed / 16.95s** 后补只读停点；
  [原 JUnit](evidence/2026-10-27-session-recovery-09-observe-red.xml.gz)。
  旧会话已 checkpoint unknown 的三分支，查询会自动推进下一确认，
  **3 failed / 39.58s**；[原 JUnit](evidence/2026-10-27-session-recovery-09-old-unknown-red.xml.gz)
  保留，随后纳入同一个只读停点，不改变同会话正常 SOP。
- 组合中真实 G3 个人预算专用采用先于恢复报 `BUDGET_INPUT_STALE`：采用已持久化，
  G3 发布推进 revision 后平台 `budget_inputs.completed_snapshot._strict` 仍要求原 dispatch
  revision。已报中控，保持失败测试，不在 Cross 放宽 F10 来源/CAS。其原 trace 位于
  [中间 JUnit](evidence/2026-10-27-session-recovery-09-controls.xml.gz)的 budget 用例。
  该中间批次为 **5 failed / 16 passed / 145.25s**，另外四失败是测试补丁使用了 pytest
  的相对模块别名、未注入实际注册 Cross 类（已改绝对 `app.modules.cross.entry`），
  不列作四个产品缺陷；修后最小真实重启与取消 **2 passed / 13.50s**。

gzip 均为原 XML 无损压缩，解压字节比较通过，raw SHA256 见
[摘要清单](evidence/2026-10-27-session-recovery-09-hashes.json)。中间检查不冒称本票最终全套。

初始基线为平台 PR #323 最终 `5bcc8551`；本票仅拥有 Cross 目录。以下是实际组合探针，规划器为明示替身，其余 Harness/Cross/安全/存储/模拟银行真实。未写作新真实模型或页面验收。

## 两个独立缺口

1. `CrossEntry.recover_session` 只改 session 后 advance；生日 gate/verify 的 advance 返回缓存旧卡。平台 provider 正确拒绝旧会话确认/验证，结果为 `DEPENDENCY_UNAVAILABLE`。Cross 应重建当前会话交互。
2. 冻结已确认、正在验证时，安全侧已有 `pending_freeze` 限定授权。若只修缓存、让新会话 gate 重查，会为同 freeze operation 生成新会话、新 confirmation_version；再批准后 `grant_release` 正确因原授权身份冲突拒绝 `OPERATION_CONFLICT`。不能为通过恢复删除唯一/身份约束。

## 最小提供接缝

建议复用已批准 G2 的安全撤离与平台新尝试能力。安全方决定公开入口及返回结构，Cross 不读写安全私表或复制判断。

- 可信绑定：user、round、task、源会话、目标会话、原 operation、action_revision、原确认 ID/version、原挑战引用、原限定授权 ID。新会话新确认不批准旧会话权限。
- 无执行 claim 且银行挑战可明确退休、旧限定授权仍 `pending_freeze` 时：在既有安全竞争边界内证明未提交，退休旧动作/挑战、使旧 pending 授权失效并保留历史；平台随后才能按已 sealed 的原尝试创建新 attempt，重新确认/验证。Cross 不自行改 operation。
- claim 已存在（processing/unknown/completed 都算）或银行结果不确定：只返回必须观察原操作；不退休、不换号、不新冻、不改写已有订单/付款或收尾事实。
- 迟到旧确认/验证码/人脸回调及旧 grant/bind 路径必须不能重新激活已退休原动作。缺失/矛盾/依赖不可用明确拒绝或暂停，不能当作“未提交”。
- 原限定授权、旧确认版本关联、旧挑战状态、原操作及审计保留。已有真实冻结及其有效收尾权不能被当作未提交作废；不退款，不追加资金。

## 真实探针应核对的事实

冻结验证等待：原执行 claim 为 None，银行尚无冻结账务效果；旧挑战 pending；旧限定授权身份为 S1 / 原确认版本 / 原 freeze operation / `pending_freeze`。迁到 S2 后，公开 freeze_check 生成 S2 / 更高确认版本，operation 仍为原号；批准后 grant 出现身份冲突，原授权/挑战/账务不变。

这仅说明“刷新卡”不足以闭环；不是安全策略批准、不是跨会话授权重绑的实现。已执行/未知分支仍须单列原号核实回归，不能据这个无 claim 样例推广。

## 2026-10-27 实测

`python -m pytest backend/app/modules/cross/test_birthday_session_recovery.py -q`：**1 failed / 1 passed，14.53s，exit 1**。新会话应重建冻结确认的目标用例失败于 provider 的旧卡拒绝 `DEPENDENCY_UNAVAILABLE`；负向诊断用例通过，真实重查生成 S2 / 更高确认版本，随后真实 grant 明确 `OPERATION_CONFLICT`，旧授权、旧挑战、claim=None 和银行零新增账务均保持。

[原始 JUnit 无损归档](evidence/2026-10-27-session-recovery-09-before.xml.gz)保留原始失败 trace，解压与原文件字节一致。未修改生产 Cross SOP，未移除安全检查，待提供方接缝后实现并重跑；不能把这个负向用例通过写成恢复完成。
