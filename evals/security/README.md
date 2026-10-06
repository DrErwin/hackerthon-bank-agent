# 安全评测集接入说明

负责人：Ringo  
版本：v0.1，2026-10-07  
交付状态：首批代表性用例设计及合成数据，自动化待实现，应用安全测试未运行。

归属与编写规范见[评测集指南](../README.md)。本轮按用户要求提交独立PR，仅修改evals/security/；契约、后端实现和版本签核均保留现状。

## 入口与规模

优先阅读[用例正文](安全评测集-v0.1-2026-10-07.md)。118个主用例中，117个有判定依据，1个为精确到期边界待补；参数展开共253个实例，结果模板按轮次展开为309行，其中308行为基线计划。

| 文件 | 用途 |
|---|---|
| 用例正文 | 业务行为、前置条件、测试刺激及判定说明 |
| [cases.jsonl](cases.jsonl) | 每行一个主用例，稳定ID与独立参数变体 |
| [fixtures.json](fixtures.json) | 合成主体、金额、时钟及记忆别名，需要映射到可信夹具 |
| [coverage.csv](coverage.csv) | R01至R09、公共验收及PRD编号关系，显式保留S07至S09缺口 |
| [run-results-template.csv](run-results-template.csv) | 初始仅NOT_RUN或PENDING_SPEC，实跑时复制并回填 |
| [source-manifest.json](source-manifest.json) | 七份仓库来源的路径、Git摘要、来源提交及初稿追踪 |

来源按仓库docs的冻结v1核对，来源提交为`5d035e50e5d5031eff80f3bf8d608f5c9b09c9ac`。该提交标记文档来源，实际运行另填代码提交及模型、策略版本。F37/F38已有契约；三条诱导话术已有01 §9.2高风险依据，其实际检测结果仍需取证。

## 当前版本与交付边界

v0.3优先普通转账的公共安全，依据[实施计划](../../docs/versions/v0.3.0/implementation-plan.md)和[评测交付包03](../../.scratch/transfer-agent-framework/packages/03-v03-evaluation.md)。本PR提交用例和数据准备，交付包领取、拆票及联合验收记录另按团队流程补齐。

| 范围 | 当前用途 | 执行依赖 |
|---|---|---|
| 转账公共权限、确认、验证、恢复及秘密保护 | v0.3优先接入 | 公开安全入口、可信主体及独立银行记录 |
| 账单明细、导出和联动私有工具 | 后续版本准备 | 对应业务公开能力，按v0.4范围接入 |
| 预约、记忆管理及完整管理界面 | 保留全系统契约样本 | 按版本需求核对是否适用；公开能力缺失记Blocked |
| 风险话术识别 | 检测器端到端评测 | 实际policy_version、rule_ids及脱敏证据；固定风险夹具独立报告 |

完整验收仍需按评测指南逐规则补齐适用分支，并核对每功能至少10条、每类异常至少3条的下限。当前118个编号代表已有设计规模，数量本身不能证明完整覆盖。公开攻击集改编尚未开展，本批刺激均为项目规则派生的合成样本。

## 规则覆盖与缺口

下表列出代表性关系，参数编号详见正文。全部引用均待实现及待运行，完整矩阵扩充与专业审查仍待推进。

| 功能/规则及依据 | 正常 | 反例 | 边界 | 失败/恢复 | 交叉情况 | 缺口与依赖 |
|---|---|---|---|---|---|---|
| 身份归属，MAIN §4.4/6.3 | SEC-P-001 | SEC-A-001/002 | SEC-A-003 | SEC-A-004 | SEC-A-006/007 | 平台提供两个可信合成主体，固定演示用户保持原口径 |
| 六种裁决，SECURITY §2/S01 | SEC-D-001 | SEC-D-005 | SEC-D-008 | SEC-D-006 | SEC-D-007 | 受控裁决夹具及终止事实 |
| 逐动作确认，CONFIRM §1/R02 | SEC-P-002 | SEC-C-001/002 | SEC-C-013 | SEC-C-014 | SEC-C-004/012 | SEC-N-008精确到期及并发待核对 |
| 基础验证，CONFIRM §1/3/R03 | SEC-V-012 | SEC-V-001/002 | SEC-V-004 | SEC-V-005/015 | SEC-V-003 | 验证专用输入与无秘密观察端 |
| 双因子，CONFIRM §1/3/S06 | SEC-V-010 | SEC-V-006/013 | SEC-V-008/009 | SEC-V-007/011 | SEC-V-016 | 完整方法与时间边界按参数逐项运行 |
| 四类威胁，PRD §9/TRANSFER §9.2 | SEC-P-006 | SEC-T-003至015 | SEC-T-014 | SEC-D-006 | SEC-T-015 | 实际检测器取证及误拦样本扩充；正常文本与攻击分开统计 |
| 执行器与银行，BANK §2/R05 | SEC-P-002 | SEC-E-001/002 | SEC-E-006 | SEC-R-001/002/010 | SEC-E-003/007 | 许可表示受控执行资格，具体传递方式沿现有实现 |
| 管理权限，MAIN §6.8/R06 | SEC-M-006 | SEC-M-001/003 | SEC-M-004/007 | SEC-M-005 | SEC-M-002/008 | 独立管理员及在途记录 |
| 脱敏与审计，MAIN §4.5/R07 | SEC-L-004 | SEC-L-001/002/006 | SEC-L-003/007 | SEC-L-005/SEC-R-009 | SEC-M-006 | 全部旁路出口观察端，证据缺失按Blocked记录 |
| 导出权限，MAIN §6.7/R08 | SEC-X-001 | SEC-X-003/004 | SEC-X-007 | 缺用例：生成故障及部分文件 | SEC-X-002/005/006 | 账单公开能力就绪后扩充，当前用于后续准备 |
| 记忆与资源，MAIN §6.9/7.6/R09 | SEC-N-007/v01至v02 | SEC-N-001/002/003 | SEC-N-007/v04至v05 | SEC-N-007/v06至v07 | SEC-N-004/005/006 | 受控memory适配及缓存观察端；模糊意图为v08 |
| 限定释放，SECURITY §3.1/S07 | 缺用例 | 缺用例 | 缺用例 | 缺用例 | 缺用例 | Ringo补独立收尾用例，平台和银行提供事实接口 |
| 会话及授权快照，SECURITY §4/S08 | 缺专项用例 | 缺专项用例 | 缺专项用例 | 缺专项用例 | 缺专项用例 | 扩充操作者/目标会话与重置后快照回放 |
| 验证摘要，CONFIRM §1/S09 | 缺专项用例 | 缺专项用例 | 缺专项用例 | 缺专项用例 | 缺专项用例 | 扩充来源、金额、收款人、开户行及版本一致性 |
| 用户结果体验，PRD §14/16 | SEC-P-002 | SEC-P-005 | SEC-P-006 | SEC-R-001 | SEC-P-004/007 | 页面证据及提示人工复核按对应场景接入 |

覆盖CSV的case_ids空值表示已登记的缺用例，不能计为覆盖或Passed。其他非空关系也仅表示追踪，完整性仍按上述方向及功能条件逐项检查。

## 八字段模板映射

JSONL及正文承载统一八字段的信息，自动化函数保持空值，方便后续适配：

| 指南字段 | 本集字段或位置 |
|---|---|
| 编号 | id，已发布编号保持稳定 |
| 业务维度 | group、title、scenario及kind |
| 映射依据 | source_refs、review_ids、acceptance_ids及prd_acceptance_ids |
| 前置环境与数据状态 | preconditions及fixtures.json |
| 用户指令/输入 | steps中的具体刺激；API用例按步骤替换目标引用 |
| Agent预期交互 | expected中的等待、澄清、拒绝及恢复行为 |
| 预期结果与硬性断言 | expected、must_not、observations及oracle_plan |
| 自动化映射与状态 | automation_mapping.status=NOT_IMPLEMENTED；test_function=null；execution_status单独记运行状态 |

parameter_sets按独立实例展开，各轮次重建前置条件。steps为逻辑操作说明，API参数及测试函数映射待实现，当前JSONL无法直接作为自动化测试运行。

## 接入与验收

1. 先核对source-manifest的Git来源及当前契约差异，再将fixtures别名映射到可信后端；预设risk_level只允许受控夹具使用。
2. 建立公开API、安全执行链和审计观察端，资金断言另核对模拟银行操作记录及账本。所需事实取不到时记BLOCKED。
3. 绑定测试函数并记录automation_mapping，先运行清单中的26个smoke主用例，再运行本版本全部适用基线。原始话术检测与固定风险流程约束分别报告。
4. 从结果模板复制实际运行记录，填写代码提交、模型配置及策略版本。断言违反记FAIL；复测新增记录并填写retest_of。
5. 补S07至S09专项用例与导出失败分支，收口SEC-N-008；关键业务规则变化交Erwin决定。完成本目录评测后，版本负责人汇总联合验收证据。

有限样本的零违反仅支持该运行版本及已测范围。当前文件结构检查通过，应用安全用例尚未运行，安全签核与真人批准另行记录。

## 数据读取与输出安全

PowerShell读取示例仅解析数据：

```powershell
$securityCases = Get-Content -LiteralPath '.\evals\security\cases.jsonl' -Encoding utf8 |
    ForEach-Object { $_ | ConvertFrom-Json }
$securityCases |
    Where-Object { $_.suite -eq 'baseline' -and $_.priority -eq 'P0' } |
    Select-Object id, title, test_level
```

CSV使用UTF-8 BOM。公式型测试刺激在结果CSV的variant列加文本前缀，真实载荷从cases.jsonl读取。认证秘密仅由专用可信夹具处理，结果和缺陷材料保存占位符；网络标记eval.invalid仅供隔离测试观察，实际银行和真实用户数据保持排除。

