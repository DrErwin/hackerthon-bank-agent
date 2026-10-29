# v0.5 英文密码标签保护补口

Status: merged — PR #270 已合入 `b1382c2`；#271 已关闭，最终接受另记。2026-10-29 核对，最新结果见[v0.5 完成情况](../../docs/versions/v0.5.0/completion.md)。

原规格状态（历史）：implemented — Erwin 已批准合入及计费本地验证例外，待中控执行；CI 实际仍未启动，不记绿 CI
Owner: Erwin（授权执行对话，AI 实施）
Accepted by: Erwin（本轮授权：Issue #271，单目录实施）
Accepted at: 2026-10-25
Source issue: [Issue #271](https://github.com/DrErwin/hackerthon-bank-agent/issues/271)
Related scope: [v05-observer-seams 规格 S4/S5/S7](../v05-observer-seams/spec.md)

## Problem Statement

自由文本中的 password、passwd、pwd 标签未进入共享审计秘密规则，导致输出探针、导出秘密探针和审计脱敏同时遗漏。原有聊天门有单独保护，不能替代导出和审计入口的修复。

## Solution

在现有共享规则补上独立英文标签，要求标签后有冒号、等号或中文系词和实际值；无值的安全教育句保持原文。保留原有中文及其他秘密规则。

## User Stories

1. 用户收到回复或导出文件时，英文密码标签后的值不会被当作普通文本放行。
2. 用户阅读不含密码值的安全提醒时，提醒不会被误拦或改写。
3. 审计查看者回放证据时，只能看到脱敏值，重复检查脱敏结果不会重新报出秘密。

## Implementation Decisions

- 唯一实施目录为 `backend/app/audit/`；复用输出探针和审计脱敏已有的共享规则。
- 英文标签不匹配其他单词或下划线字段的子串；匹配不区分大小写。
- 显式分隔符后的非空值按现有秘密值形状识别，包含纯符号密码；不添加字符种类或最短密码长度要求。空引号、空括号及标点空值不视为实际值。
- 不修改 Harness、安全策略、API、公共契约、确认或资金执行。

## Testing Decisions

| 编号 | 核心场景 | 验证 |
|---|---|---|
| E01 | 三个英文标签带实际值 | 冒号（含全角）、等号、是/为；大小写；三入口判定与脱敏结果一致 |
| E02 | 安全提醒、空值、相似单词 | 无凭据命中，原文不变 |
| E03 | 已脱敏文本与持久化回放 | 无原值落盘，回放与脱敏一致，脱敏结果不再命中 |
| E04 | 中文与其他秘密、聊天及导出 | 复跑现有 audit、聊天、导出相关测试及后端全量测试 |

测试使用虚构值和 pytest 独立临时数据库。仅报告实际验证：函数/持久化、离线 Harness、进程内 HTTP 分层记录；不调用真实模型，不冒充页面或真人验收。

## Out of Scope

Issue #216 整体收口、检测器装配、样例扩充、真人安全签核、PM 接受和总进度更新。不接管其他 PR。

## Further Notes

- 2026-10-25 已读取本机 to-spec、to-tickets、implement、code-review；前三级文件标记 disable-model-invocation，本会话未提供相应原生 Skill 调用入口，按明确授权执行其流程，不声称原生调用成功。已有技能未升级或覆盖；来源基线以仓库开工说明为准，本轮未重新核验安装来源提交。
- 本轮已明确补一张单目录最小票，无新增业务或安全裁定；无需重复询问粒度。总跟踪与 completion 由中控维护。
- 安全审查使用独立 AI 子代理，不能记为 Ringo 本人签核。
- 交付：[PR #287](https://github.com/DrErwin/hackerthon-bank-agent/pull/287)。本票 E01—E04 实证见[实施票](issues/01-english-labels.md)；不收口 #216 或整体隐私验收。
