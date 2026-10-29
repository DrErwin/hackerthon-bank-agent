# 15：完整生活目标与单项业务入口区分

Ticket ID: v05-cross-platform/15
Package: [v05-cross-linkage/packages/01-platform-bank：公共接缝与模拟银行](../../v05-cross-linkage/packages/01-platform-bank.md)
Spec: [Issue301路由规格](../research/issue301-routing-spec.md)
Source issue: [Issue #301](https://github.com/DrErwin/hackerthon-bank-agent/issues/301)
Type: 开发
Owner: Erwin
Directory: `backend/app/agent_platform/`
Status: merged — PR #303 已合入 `57a2fd7c`；后续真实批与页面减支已另记，原 S01 Failed 保留，完整验收未完成。CI 计费未启动。2026-10-29 核对。
Accepted by / at: Erwin指派Codex；2026-10-25。
Blocked by: None；Cross/订阅其他目录的必要缺口如实回交，不越界。
Branch: codex/v05-platform301-routing；base 855497fa16616595eac8cfac9013ec701ffe942d。
Core scenarios: R01—R06，见[场景框架](../research/issue301-routing-spec.md#场景与验证框架)。

## Acceptance criteria

- [x] 读原完整输入/目录/回包/派发，关联Issue301；区分模型选择、调用/解析异常及订阅原话解析，不预设提示词唯一根因。
- [x] 根据实际缺口作最小平台修复；按完整生活目标、明确单项业务、只读查询和澄清的原则区分，不堆原句关键词。
- [x] 不替模型硬改成固定cross、不把全部退订送联动；目录缺能力时不杜撰入口；不改安全规则或生日待定政策。
- [x] 有针对性回归与受影响原路径；保持银行0写入的真实模型小样路由证据，失败保留，不宣称页面E2E完成。
- [x] 两位独立Standards/Spec子代理审阅，必修关闭；独立PR附精确head、验证层和残余，不自合并。

## Verification / evidence

本票验证计划见规格R01—R06；原失败批次不变。自己的诊断/新批次证据在本组research/evidence下，后续追加实际命令、结果与审阅，不复制共享状态。

2026-10-25：[PR #303](https://github.com/DrErwin/hackerthon-bank-agent/pull/303)为本票独立Draft交付；代码受审至af275410e195b7a3d479591edc620d4e8a089e35，后续仅票据/审阅回填，精确当前head以PR为准。[诊断与分层验证](../research/issue301-diagnosis.md)、[独立审阅](../research/issue301-review.md)均可核对。
原真实S01仍Failed；合入后由原E2E对话新批次复验。订阅“停止”误解析由Issue302另线处理，本票不接其目录或声称已修。没有真人安全/PM体验接受，不自合并或复用CI例外。
