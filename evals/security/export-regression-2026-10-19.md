# 票04：公开导出安全回归

Owner：Ringo。对应[v04-ringo-security/04](../../.scratch/v04-ringo-security/issues/04-details-export-regression.md)。AI按Ringo授权执行，真人专业批准另记。

## 范围与复用

`export_regression.py`复用现有app/api的10项测试，新增8个检查实例，只改evals/security。入口使用真实FastAPI/TestClient、导出服务和隔离模拟银行，授权及风险回调为受控替身，L03卡片来自既有契约夹具。它验证平台F21至F24，真实账单L01至L03及生产检测器另验；18项与全集345行属于不同口径，结果分别登记。

| 范围 | 依据或现有测试 |
|---|---|
| 卡片归属、捕获任务绑定 | test_f21_returns_the_report_card_to_its_owner_only、test_report_capture_is_bound_to_an_owned_task |
| 普通导出与明细验证 | test_f22_card_export_downloads_without_reverification、test_f22_details_export_requires_fresh_verification |
| 到期、取消及重发 | test_details_export_expires_with_its_challenge、test_details_export_cancels_along_the_same_platform_task、test_details_export_survives_code_resend |
| 失败与他人访问 | test_details_export_fails_after_three_wrong_codes、test_exports_stay_invisible_to_other_users |
| 无验证码泄露 | test_details_export_never_stores_or_returns_the_verification_code |
| 同会话重复下载、同号改变kind | 新增test_export_boundary前两项，对应PR #159设计的SEC-X-009、X-010边界 |
| 已验证明细跨用户下载 | 本人200下载后，独立U2请求同一文件与随机不存在文件均404，资金及导出记录保持 |
| HTML转义及CSV文本安全 | 公共契约§6.7，新增HTML对照和四类公式型文本实例 |

同请求号冲突测试限定同一端点路径。当前回执键包含endpoint，改变report_id路径属于另一回执域，本票沿既有事实验证kind变化，未自行制定跨端点复用编号的业务规则。

## 运行

使用仓库backend虚拟环境，在可导入当前backend/app的环境中运行：

```powershell
$report = Join-Path $env:TEMP ('security-export-' + [guid]::NewGuid().ToString('N') + '.json')
python evals/security/export_regression.py --output $report
```

报告只含测试编号与结果、来源哈希及环境边界，响应体、验证码和失败堆栈均排除。输出须为工作副本外的新路径。失败返回非零退出码；首次失败证据保持，修复后另存新报告。

2026-10-19首次公开链路实跑：13 Passed / 4 Failed。失败均为CSV单元格公式型文本原样出现在下载，已建[Issue #161](https://github.com/DrErwin/hackerthon-bank-agent/issues/161)交Erwin修复api目录。当前重现测试保留失败，PR先作Draft，等待实现修复后复验，不将其改为忽略或预期通过。合法同会话重复下载与HTML转义对照均通过。

Spec复核补充了已验证明细跨用户下载的缺口，Standards复核补充报告器setup阶段skip应记Blocked。两项均已返修，报告器5项单元测试通过；最终公开链路18项为14 Passed / 4 Failed，原始失败批次保持。CSV缺陷仍待Erwin修复。

代码基线为远端main ecf90d0加PR #149新head fad93a3（本地后端a74f9d5）。首次报告见[导出证据说明](evidence/2026-10-19/export-README.md)。本轮真实模型调用0次。

## 修复后的独立复验

2026-10-19，Issue #161 的修复 PR #168 已合入。独立更新 API 来源至 main `e43765a0dec7737a64fd235e3a65c21a0b265656` 后，原 runner 的18项全部通过，四种公式型文本均作为文本导出，其余14项保持通过。旧批次的4项 Failed 完整保留，复验关联及原始报告见证据说明。本结果仅关闭本专项已观察缺陷，真实账单和生产装配继续分别验收。

## 2026-10-20 前置空白/制表符变体补充

独立审查的 1 项必修要求补齐 #161 的「前置空白/制表符」公式变体。`test_export_boundary.py` 的公式型文本参数由 4 组扩为 6 组（新增 `" =1+1"`、`"\t+1"`），并把断言从「不以公式符起头」加强为「单引号前缀后逐字保留原文」，runner 合计 20 项。

2026-10-20 实跑：20 项 **20 Passed / 0 Failed**，报告见 [2026-10-20 supplement](evidence/2026-10-20/2026-10-20-offline-export-boundary-supplement.json.gz)，解压后 sha256 `7432C090946D2408C3109BDB7639B1AA8E412CC3281AE77D468BE0836A7A4AC0`。来源基线为报告产生时的 main `25b0738`；其后合并 #149 只改 `backend/app/security`，不影响本专项记录的文件哈希；`backend/app/api` 与 #161 修复版本自 `e43765a` 起未变。原 18 项 retest 报告（`036109E2…`）保持历史，不重写。本批仍为受控 L03 夹具与平台替身，不代表真实账单 L01—L03 或生产检测器通过。
