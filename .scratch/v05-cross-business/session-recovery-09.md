# 票09：生日会话恢复的安全提供需求

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
