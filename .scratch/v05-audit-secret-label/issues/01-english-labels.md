# 01：英文密码自由文本标签一致保护

Ticket ID: v05-audit-secret-label/01
Package: 本轮独立缺口修复，无新增交付包；关联 [v05-observer-seams 输出观察](../../v05-observer-seams/spec.md)
Spec: [英文密码标签保护补口](../spec.md)
Core scenarios: E01—E04（见 spec）；确认、取消、恢复不适用于只读探针改动，复用既有后端回归覆盖。
Verification: 三公共入口一致性、无值提醒、审计落盘与回放、现有中文及秘密保护、聊天和导出回归；后端全量与必要仓库静态检查，实际证据见 Comments。
Type: 开发
Owner: Erwin（授权执行对话，AI 实施）
Directory: backend/app/audit/
Status: in_progress
Blocked by: None
Source issue: [Issue #271](https://github.com/DrErwin/hackerthon-bank-agent/issues/271)
Claimed by: Erwin（授权执行对话）
Claimed at: 2026-10-25

## What to build

password/passwd/pwd 后有实际值时，输出及导出探针报告 credential，审计自由文本脱敏删除原值；安全教育句没有值时正常保留。

## Acceptance criteria

- [ ] E01：三标签 × 冒号/全角冒号/等号/是/为及大小写，三入口结果一致。
- [ ] E02：无值教育句、空白值、标点空值与相似单词放行。
- [ ] E03：脱敏幂等；真实审计写入/回放/导出不含虚构原值。
- [ ] E04：原有中文与其他秘密测试、聊天及导出回归不退化。
- [ ] 独立子代理分别审查仓库规范和原始规格，必须项修复复验；代码 PR 交中控合并。

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
