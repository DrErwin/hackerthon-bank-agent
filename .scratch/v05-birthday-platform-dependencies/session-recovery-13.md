# 票13：生日敏感等待跨会话的真实平台证明

## 目标

安全330只接受平台在同一应用事务中证明原任务、会话、发布CAS与参数绑定仍一致，才允许退休原未提交尝试。平台必须在任何新会话check/新卡前固定原来源，安全封存后才关联一个新attempt；不把旧批准挪给新会话。

## 最小流程

1. 敏感卡每次在原严格发布CAS之前封存平台私有 action/option 摘要，仅hash，不把配送原文复制入Cross checkpoint。Harness 已认证目标会话并授权任务能力后，校验精确 G3 封存源并对照该摘要，再固定原 action、参数摘要、确认ID/version、发布ref及原任务revision，随既有会话迁移CAS记录；不读取或修改 Cross 私有状态。旧敏感源没有摘要或参数已偏离当时封存值，明确SOURCE_UNAVAILABLE，保留历史，不默认回补；这限制了这类旧敏感任务自动跨会话恢复。
2. 目标会话迁移完成后，在 Cross 恢复回调/新check前准备私有恢复回执。安全上下文持目标session与原op/revision，确认字段None；原会话/旧确认作为显式冻结参数传入安全330。
3. begin/seal 的 validator 只使用安全传入的 SQLite connection 核对当前任务user/round/session、准确原发布ref/参数摘要、持久task_session_transitions记录、迁移marker及受理CAS。外来版本漂移、异参数/主体/会话、任务终止或依赖失败均拒绝，不用另连数据库的布尔task resolver冒充证明。
4. 银行证据只能由真实 `gateway.retire_action_challenges` 对原op/revision生成。安全受理、封存、审计使用真实UTC，业务编辑时间仍属于业务钟。
5. sealed后一次task CAS保存新attempt、原history和恢复回执中的唯一关联。重试/重启复用同一关联，不能因封存后/关联前后中断再造第二个UUID；旧动作和挑战仍不能复活。
6. 安全认定已有claim/active/未知时不调用银行退休；银行无法证明未提交时不封存退休。两者均返回明确的原号观察投影，不换号、不重冻、不退款。已付款、订单、原限定授权及历史保留。

## 对Cross09的消费接缝

提供仅限当前可信任务的只读恢复投影：`status=fresh|observe`、原operation/action/revision，以及fresh时唯一replacement operation。Cross09据此运行自己的恢复SOP：fresh重查新确认/验证，observe沿原pending目标/操作查询；本票不在平台改写 Cross holding/pending，也不把当前缓存旧卡的消费方当作已修。

## 验证

- 六种冻结/下单/核销确认及验证等待，以真实封存来源、安全状态、银行退役证明验证新attempt/历史/唯一关联；模型仅明示提案替身。
- 在 begin→bank→seal 间改变CAS、参数、目标session/主体，或竞争claim，证明失败不能得到新attempt。
- 封存后关联前、关联后回执前中断，原目标会话重试不换关联；业务前/后拨不污染安全证据时间。
- 原Cross09 1fail/1pass和其他历史失败不覆盖。当前Cross缓存旧卡仍必须被provider拒绝；完整Cross会话闭环另票验收。

## 当前验证检查点

- 初始真实冻结确认恢复缺提供投影的红例：1 failed / 7.91s；原始JUnit保留。
- 首轮完整提供方六阶段 6 passed；添加CAS/参数/发布/会话/终止、seal/link断点、claim与真实active冻结及真实时钟后，连同既有14项恢复回归先取得40 passed。这里没有把Cross缓存卡改作当前卡。
- 加入不可变发布摘要与旧敏感源限制后，定向42 passed / 66.23s（28项provider + 14项既有恢复）。为验证新增来源拒绝用例确实能抓住“只冻结当前快照”的问题，在隔离测试中暂用前一版未核对封存摘要的消费函数，两个真实组合用例均失败（2 failed / 7.34s）；随后恢复生产源码，SHA256逐字节一致。该来源防线反向验证是测试构造，不冒充新的历史生产失败。
- 恢复生产来源防线后，以固定 `4dd051a5407adf8f46f09970ab4407e18beb96ec` 完整运行 `python -m pytest backend/app/agent_platform -q`，独立临时目录；结果 **423 passed / 13 skipped，329.95s，exit0**。原进程未重启或终止，13个既有端点skip不计通过。[原始整套JUnit](evidence/2026-10-27-platform13-full.xml)。受测平台树 `b200cb4c1565b34eee5a2d0d62f9d6d1ff54bfb7`，后续只归档证据，不改源码。
- 未调用真实模型或写原失败库；不是页面验收、完整Cross09会话闭环或真人安全签核。中控Standards在固定4dd代码上0必须项，Spec独立审查/远端CI/合入另列。
