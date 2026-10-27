# v05-birthday-platform-dependencies/10：生日任务跨会话恢复

Ticket ID: v05-birthday-platform-dependencies/10
Package: [v05-cross-linkage/packages/01-platform-bank](../../v05-cross-linkage/packages/01-platform-bank.md)
Spec: [本组规格](../spec.md)，补充规格见下方
Type: 开发
Owner: Erwin（v0.5 统一负责）
Directory: `backend/app/agent_platform/`
Status: ready_for_review — provider 实现及平台目录 387 passed / 13 skipped，待中控两轴审查与合入；敏感等待消费方 SOP 另票。
Accepted by: 本对话 AI，依据 2026-10-27 用户完成非比赛资料任务的授权及中控委派
Accepted at: 2026-10-27
Blocked by: None（既有 G3 封存/发布、Cross 恢复入口和会话迁移已合入）
Core scenarios: SR01—SR05
Verification: 隔离真实组合与受影响 Harness 回归，模型为明示替身；不写作页面/真实模型验收。

## 补充规格

- SR01：本人新登录会话恢复生日任务时，读取精确的不可变已发布源，沿既有 Cross 恢复入口建立新会话交互，再通过同一缓冲、封存和严格 CAS 发布接缝；不得读写默认 latest namespace。
- SR02：等待确认或验证时恢复，平台须检查消费方返回的交互属于新会话；返回旧卡时明确拒绝、不发布。Cross 的敏感等待卡重建另票消费，本票不篡改 Cross 私有状态。原操作、已付款事实与未知结果仍沿原号核实，不重复创建采购或付款。
- SR03：恢复发布中断后，原恢复 marker 关联同一转换；重试可复用封存 winner，不重新执行 Cross 或重做银行写入。
- SR04：其他用户/轮次、缺失或篡改源、其他在途输入/编辑在迁移前拒绝；任务与发布源不变。
- SR05：legacy 无 G3 的原恢复保持；缺不可变来源的旧任务编辑仍明确拒绝，不能以可变默认状态伪造历史来源。

本票只接平台既有恢复能力，不改公共契约、API、安全规则、存储格式或 Cross SOP。API 的原 request 自动续做另归票 11；风险政策不在本票。

API11 所需只读接缝一并交付：`BirthdayHandoff.find_input_conversion(trusted, request_id)` 返回原完成投影 `PublicationOutcome`、`"pending"` 或 `None`；API 不复制平台私有摘要算法，不把任意旧 request 当作已受理。

## Comments

- 2026-10-27：中控批准本票最小单目录计划；分支 `codex/v05-g3-session-recovery`，基线 `152d61d4`。
- 2026-10-27：已交 [Draft PR #323](https://github.com/DrErwin/hackerthon-bank-agent/pull/323)；[实际验证与边界](../recovery-10-verification.md)。原输入查询供 API11，敏感卡缓存缺口另交 Cross 消费方，不在平台复制 SOP。
