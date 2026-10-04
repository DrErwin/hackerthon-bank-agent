# 票10新对话交接（2026-10-05，北京时间）

## 用户最新授权

用户明确要求：先由AI代替Ringo审查并合并PR #73/#74，然后开新对话完成v03-transfer-eval-fixes/10；Prompt不要变成逐场景打补丁，应简洁统一；测试完成后可以合并。用户不需要再细化技术规划。旧paused不再阻止票10实施；本次允许实现、修改Prompt/模型接入代码、必要验证、独立PR、审查通过后合并。记录用户授权AI代审，不冒充Ringo本人或专业安全验收。不要重复索取已提供的例行实施/合并批准。

## 起点与文档

最终主线提交和PR合并证据见同目录online-diagnosis-20261005.md的最新追加段。读取AGENTS.md、docs/agents/delivery-workflow.md、git-workflow.md、issue-tracker.md、docs/principles/03-review-and-merge.md、02-security-platform.md；复用已有spec.md和issues/10-model-transfer-missing-input.md。新对话先领取10并更新in_progress，保留历史暂停/诊断记录。此前11、12已独立交付，不把它们重新实施或混进模型PR。

Directory: backend/app/agent_platform/；Owner: Erwin（v0.3已有执行安排）。一张票/分支/PR一个目录，代码、测试都落此目录。需要其他目录新能力时单独问题记录/票，不能顺手修改产品API、契约或evals。不新建最终验收票。纯过程文档另按纯文档流程检查/主线发布，不混入代码PR，不运行/等待文档CI。

## 业务目标与Prompt原则

使明确转账缺项仍建立可补齐/恢复的原任务；只提取确定字段，不替用户决定金额或账户，合法转账仍进入原确认流程。

Prompt按“业务意图是否明确 → 字段是否确定 → 本轮产生单一结果”组织。重新整理简洁统一原则，避免按PAY/INP/CNF等样本逐条追加特例；具体数字、近似说法、区间、缺项等放测试。明确意图与字段完整度分开；未知联系人交后续银行查询，缺失/不确定字段留空。金额是否合法、银行结果、权限与确认由确定性代码负责。不得让模型授权/执行资金。

## 已证实缺陷与Issue

- Issue #68：https://github.com/DrErwin/hackerthon-bank-agent/issues/68。PAY11/INP08实际reply_only导致无任务；正确缺项proposal回放Passed。INP14两次reply_only，RCV21一次reply_only一次proposal；同一清晰转账输入仍有分类不稳定。不是所有追问都可用普通聊天代替任务。
- Issue #69：https://github.com/DrErwin/hackerthon-bank-agent/issues/69。CNF10/CNF15固定各2次复现为1 Passed/1 Blocked；真实工具序列propose_transfer成功后又reply_only成功，outcomes数量为2，触发MODEL_PROPOSAL_AMBIGUOUS。已有无网络最小回放。优先核实现有框架工具结束/返回能力，一次有效结果后结束本轮；继续拒绝冲突结果。禁止取首个/末个候选放行或自动重规划。
- Issue #70：https://github.com/DrErwin/hackerthon-bank-agent/issues/70。INP03实际payer_account_id="null"字符串穿过schema，银行precheck ACCESS_DENIED，task.failed；只改真正null/None即可完整场景Passed。工具字段空值约定及接入校验应统一，不能默认A1或放宽银行权限。
- 原INP14/RCV21 ValueError只有类名，未保存数量/阶段，历史具体原因未知。最后INP09单次在线有安全错误码MODEL_PROPOSAL_AMBIGUOUS，说明未形成恰好一个结果；该次未保存数量，不能断言必然是双工具。
- 原合法十六元、缺金额恢复/首检查点恢复仍按票10既有验收覆盖，不能只修当前9项后漏掉原scope。

本次不修专业TF-VFY-16：Ringo真实攻击来源材料缺失，继续单列依赖。银行事实、敏感确认、资金/隐私红线不放宽。

## 现有证据（勿覆盖）

原真实GLM153报告：.mnemon/online-retest-20261005/RESULT.md及full/20261004T161318608992Z/report.json，143 Passed/4 Failed/1 Error/5 Blocked。
同主线离线：.mnemon/sync-retest-20261004/RESULT.md及offline-browser/20261004T152641690100Z/report.json，152 Passed/1 Blocked。离线固定候选不替代模型理解。
诊断和实施：.mnemon/online-diagnosis-20261005/{replay,seams,minimal,live-probe,implementation-replay,implementation-live}.json。live-probe为固定8次，3 Passed/3 Failed/2 Blocked；原始安全工具序列及所有失败保留。
原五项输出的最后组合回放：PAY11/INP03/INP08 Failed，INP09/BNK01 Passed，原INP03 Error归还真实业务Failed，均无银行提交/出流。INP03正确空值对照按显式确认后成功提交一笔，不能把合法对照混算为失败副作用。

## 实施与验证流程

先应用diagnosing-bugs建立已经执行的红色反馈回路，按已有最高真实HTTP/Harness/任务/银行账本接缝回归；implement按票开发，code-review双轴复核及资金/隐私安全代审。不要凭在线失败+离线通过就统一归因LLM。

对规划边界只保存白名单错误码、结果数量/工具名及必要阶段，不落原始供应商回复、异常文本、密钥或完整受控号码。若四个异常不是同根因，分别说明。尽量使用现有模块接缝，不新造大型模型评测架构或通用fallback。

真实模型定向运行前声明固定配置、样本集、每样本次数与输出目录，保留每次结果，不反复跑到绿。模型相关失败消除后，按票10现有批准分母和完整范围做一次必要整体验证；缺项8项要求100%，标准21项及153样本保留。不随便减少范围、修改判据或以固定proposal替代GLM。外部专业材料项Blocked单列，不让其冒充模型修好，也不把它变成独立程序修复的虚假前置。

达到本票代码/模型要求、AI审查无未处理问题、最终代码HEAD CI通过后，按用户授权squash合并；同步主线做针对性冒烟，更新票据/Issue/版本进度。不能把票10合并写成v0.3已验收；AF01—AF14、T01—T18及专业安全材料仍按证据核对。不要同步飞书或进入v0.4。

## 本机环境与保护

主目录D:/hackerthon-bank-agent；用户时区Asia/Shanghai。使用独立managed worktree保护主目录，不reset/clean/盲目stage/覆盖配置。读list_artifacts后可复用适合的工作区，否则创建票10worktree。新对话在local项目启动，不意味着代码必须在主目录做。

依赖Python：C:/Users/57652/.codex/worktrees/transfer-eval-suite/hackerthon-bank-agent/.venv/Scripts/python.exe，运行时显式PYTHONPATH或现有conftest指向本轮checkout/backend，不能误用旧editable安装源码。旧依赖环境不要删除。
配置：D:/hackerthon-bank-agent/.env.local-demo.json，通过load_config读取，禁止打印内容或凭据。真实GLM-5.3/Coding Plan，temperature=0,max_retries=0；CLI run_live_eval.py --live-glm --config上述路径 --case样本 --jobs1 --output新独立目录。隔离临时库，不操作演示库；已有frontend/dist可在必要整体验证用作React证据。无端全量重跑/环境重建/新框架均不在任务内。

## 已核对的交接基线

代码主线ba77dbbf30c01e0244be58c9153807638cb43a6e已包含PR #74（2c7ecaf）与PR #73（ba77dbb）。相关代码CI均通过；主线6项平台与8项评测冒烟通过。过程文档后续提交只改变状态和交接记录；开工仍再核对最新main。
