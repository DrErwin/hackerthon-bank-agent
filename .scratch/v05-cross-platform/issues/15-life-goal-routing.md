# 15：完整生活目标与单项业务入口区分

Ticket ID: v05-cross-platform/15
Package: [v05-cross-linkage/packages/01-platform-bank：公共接缝与模拟银行](../../v05-cross-linkage/packages/01-platform-bank.md)
Spec: [Issue301路由规格](../research/issue301-routing-spec.md)
Source issue: [Issue #301](https://github.com/DrErwin/hackerthon-bank-agent/issues/301)
Type: 开发
Owner: Erwin
Directory: `backend/app/agent_platform/`
Status: in_progress — 2026-10-25中控授权，先诊断；未交付/未合入。
Accepted by / at: Erwin指派Codex；2026-10-25。
Blocked by: None；Cross/订阅其他目录的必要缺口如实回交，不越界。
Branch: codex/v05-platform301-routing；base 855497fa16616595eac8cfac9013ec701ffe942d。
Core scenarios: R01—R06，见[场景框架](../research/issue301-routing-spec.md#场景与验证框架)。

## Acceptance criteria

- [ ] 读原完整输入/目录/回包/派发，关联Issue301；区分模型选择、调用/解析异常及订阅原话解析，不预设提示词唯一根因。
- [ ] 根据实际缺口作最小平台修复；按完整生活目标、明确单项业务、只读查询和澄清的原则区分，不堆原句关键词。
- [ ] 不替模型硬改成固定cross、不把全部退订送联动；目录缺能力时不杜撰入口；不改安全规则或生日待定政策。
- [ ] 有针对性回归与受影响原路径；保持银行0写入的真实模型小样路由证据，失败保留，不宣称页面E2E完成。
- [ ] 两位独立Standards/Spec子代理审阅，必修关闭；独立PR附精确head、验证层和残余，不自合并。

## Verification / evidence

本票验证计划见规格R01—R06；原失败批次不变。自己的诊断/新批次证据在本组research/evidence下，后续追加实际命令、结果与审阅，不复制共享状态。
