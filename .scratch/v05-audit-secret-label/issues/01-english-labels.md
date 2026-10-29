# 01：英文密码自由文本标签一致保护

Ticket ID: v05-audit-secret-label/01
Package: 本轮独立缺口修复，无新增交付包；关联 [v05-observer-seams 输出观察](../../v05-observer-seams/spec.md)
Spec: [英文密码标签保护补口](../spec.md)
Core scenarios: E01—E04（见 spec）；确认、取消、恢复不适用于只读探针改动，复用既有后端回归覆盖。
Verification: 三公共入口一致性、无值提醒、审计落盘与回放、现有中文及秘密保护、聊天和导出回归；后端全量与必要仓库静态检查，实际证据见 Comments。
Type: 开发
Owner: Erwin（授权执行对话，AI 实施）
Directory: backend/app/audit/
Status: merged — PR #270 已合入 `b1382c29`；2026-10-29 核对。原验证与审查按各批记录，CI 计费未启动；实际结果与待接受项见[v0.5 完成情况](../../../docs/versions/v0.5.0/completion.md)。

原交付时状态（历史）：implemented — Erwin 已批准合入及计费本地验证例外，待中控执行；CI 实际仍未启动，不记绿 CI
Blocked by: None
Source issue: [Issue #271](https://github.com/DrErwin/hackerthon-bank-agent/issues/271)
Claimed by: Erwin（授权执行对话）
Claimed at: 2026-10-25

## What to build

password/passwd/pwd 后有实际值时，输出及导出探针报告 credential，审计自由文本脱敏删除原值；安全教育句没有值时正常保留。

## Acceptance criteria

- [x] E01：三标签 × 冒号/全角冒号/等号/是/为及大小写，三入口结果一致。
- [x] E02：无值教育句、空白值、标点空值与相似单词放行。
- [x] E03：脱敏幂等；真实审计写入/回放/导出不含虚构原值。
- [x] E04：原有中文与其他秘密测试、聊天及导出回归不退化。
- [x] 独立子代理分别审查仓库规范和原始规格，必须项修复复验；代码 PR 交中控合并。

## Comments

- 2026-10-25：已接受 Issue #271 指定范围；仅 audit 实施与本组 .scratch 文档，不修改共享总状态；不关闭 #216，不自行合并。
- 修复前：新增三入口与持久化用例 40 failed / 45 passed，确认真实漏检、漏脱敏；修复后 audit 首轮 124 passed。
- 局部回归：`python -m pytest -q app/audit/test_english_secret_labels.py app/agent_platform/test_reply_credential_gate.py app/api/test_output_observation.py app/api/test_export_secrets.py`：107 passed；含 6 项卡片/审计导出进程内 HTTP 拒绝及留痕，真实 Harness 使用离线替身规划器。全量测试、独立审查和 CI 待补。
- 额外观察（不属本票修复）：直接把 `json.dumps({"leak": "pwd 是 Dummy271!"})`（默认 ensure_ascii=True，系词变成字面反斜线 u662f）注入导出行时，下载探针不解码、HTTP 200。当前 AuditReader 导出使用 ensure_ascii=False，本票按真实生产形状验证；任意转义/编码内容的解码扫描需交中控另行评估，不在 audit 标签规则中增加 JSON 解码或跨目录改动。
- 本机系统 Python 缺少 langchain_openai，后端全量首次在收集期报 11 个依赖导入错误；已建立本 worktree 隔离虚拟环境按仓库固定依赖安装，再进行全量验证。
- 独立审查第一轮：Standards 0 必须项；Spec 发现 1 个 P1（纯符号密码被字符种类限制漏掉）。补测试复现 12 failed / 9 passed；移除字符种类限制并覆盖 `!@#$`、`____`、`****` 后，新增文件 103 passed。空 Markdown 星号可能就是符号密码，按真实值处理；无值空引号/括号仍放行。审查修复后待子代理复验。
- 复审追补：重复括号密码 `()()` / `((()))` 同样作为实际值，空包装只精确排除一个空 token。增加真实审计包（含嵌套 JSON 证据字符串）的脱敏后再探测对照，防止英文 `[REDACTED]` 在导出阶段被误报。修复相关局部 29 passed / 82 deselected；最终全目录回归与双轴复审待补。代码更新后停止旧代码全量运行，重新验证最终代码。
- 最终局部回归：`pytest -q app/audit app/agent_platform/test_reply_credential_gate.py app/api/test_output_observation.py app/api/test_export_secrets.py`：166 passed。其中新增文件 111 项（105 函数/持久化与 6 HTTP）；不含真实模型或页面验证。仓库文档链接、全量代码 compileall、差异空白检查通过。
- 最终独立审查：Standards 无必须项（74 passed / 37 deselected）；Spec 原 P1 已闭合、无新必须项（105 passed / 6 deselected）。均为 AI 审查，不代表真人安全或 PM 接受。
- 已同步最新 `origin/main` `a1e8889`，仅多出中控文档提交，代码树不变；后端最终全量运行中。
- 最终全量：在隔离虚拟环境补齐仓库固定依赖，并额外安装仅用于本地并行验证的 pytest-xdist（未更改仓库依赖文件）。`python -m pytest -q -n 4 --durations=10`：**1699 passed in 363.39s**；`python -m pytest -q ../evals/mockbank/test_mockbank_eval.py`：**14 passed**。串行慢批次中止后换为同一套完整测试，不计为已通过批次；本次最终结果以上述完整并行批次为准。
- 分层证据：新增 105 项函数/审计持久化回放与包复探 + 6 项进程内 HTTP 卡片/审计下载拒绝；局部 166 passed；全量 1699 passed 包括既有离线 Harness、确认、权限、资金防重等回归。真实模型 0 次调用；页面/浏览器 E2E、真人安全签核和 PM 接受未执行。
- 交付：[PR #287](https://github.com/DrErwin/hackerthon-bank-agent/pull/287)，已附加到本执行对话；作者不合并。合入后可解除 #271 英文自由文本标签缺口并供输出/导出联调复用，不解除 #216 整体验收或其他隐私/编码边界。
- CI：运行 [40167460403](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/40167460403)，head `8812a21707135607dba4b2cc51fcd480f7f8451e`，Repository checks 未启动任何步骤；官方注释为 recent account payments failed / spending limit needs increase。状态为失败/基础设施 Blocked，不能记绿 CI，是否适用既有例外交中控判断。
- 交付前再次同步最新主线 `9a479ea`（仅前端及其文档变化，无后端变化），最终 audit 代码与独立审查通过的 `0952119` 完全相同；仅本组材料回填最终证据。
- 2026-10-25 中控续派：Erwin 明确批准首批含 PR287 合入及计费本地验证例外；本对话仅准备并更新原 PR，中控执行合并，不扩大为 Ringo 本人签核或 #216 整体验收。
- 准备合入：在原隔离 worktree rebase 最新主线 `36f1d663b73a1511d2ddc362eb39bd4f972f0e76`。与原 head `8f205a61d4987c96e757ac05134d3e88b6d19ee2` 比较，audit 目录 tree 均为 `6a850ff49642ccb15ae08f496eaf3bb8a065568c`；audit 补丁 SHA256 均为 `fc691093740640489b7a07082faa7348d10c54bd8f5ffca636d3c8949c4566c1`，无实质变化。仍只有 audit 与本组 spec/票，没有混入503诊断材料。
- 同步后定向复验：`pytest -q app/audit app/agent_platform/test_reply_credential_gate.py app/api/test_output_observation.py app/api/test_export_secrets.py`：**166 passed in 29.52s**。文档链接与差异空白检查通过；本轮未重跑全量、未调用真实模型。1699/14 为此前批次的历史证据，不表述为本次新跑。
- 503 固定诊断 worktree/代码基线保持不动；未启动带观测全量，等待养老金297批次结束后中控明确开始信号。
