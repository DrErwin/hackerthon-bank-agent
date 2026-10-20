# 05：L03受控报告与导出接线

Ticket ID: v04-ethan-bills-backend/05
Type: 开发
Owner: 周恩宇
Directory: backend/app/modules/bills/
Status: resolved（L03 业务模块 #151 已合入；Erwin 平台票05阶段二 L03 默认运行时验收已通过，前端联合/专业安全另验）
Package: [v04-bills/01](../../v04-bills/packages/01-bills-backend.md)
Spec: [本人规格](../spec.md)
Core scenarios: [BF03/BF04/BF06](../../v04-bills/spec.md)
Blocked by: None（业务模块/真实 L03 API 报告主路径已通过阶段二）；前端账单插槽、BF01—BF07 全量及安全签核仍按票 07 / 联合验收包收口。
Verification: 三块卡片、月均/范围完整性、分享不增权；卡片普通导出、明细验证成功/失败/过期/越权；资源生成和恢复有真实证据。

## 验收

不夹带趋势/异常块，不生成无权下载；不自行复制验证码/资源权限系统。局部报告数据生成与真实可下载资源分开记录。

## Comments

### 2026-10-19：L03 模块实现与复核

- [PR #151](https://github.com/DrErwin/hackerthon-bank-agent/pull/151) 对应模块级增量；受测本地源码 `e604dbcd3faac3c01b9c357fff9d3ed90fa38335`，基线 `9741053c304a194a4c3d5ab3048f4dbb8be3b0f9`。本轮源码只改 `backend/app/modules/bills/`；已推送最终远端 [97441e68826a0268309fff561e14cc057991b05c](https://github.com/DrErwin/hackerthon-bank-agent/commit/97441e68826a0268309fff561e14cc057991b05c)，两者 Git 树均为 `59ba581ecf8c4742bb701e9cd6e808aa6df25729`，代码工作树已对齐且干净。不记录为已合入。
- 已实现 `BillsReportService.generate_report`、独立 `REPORT_MANIFEST` 和 `register_bills_report`，复用受控 B01/B08、公共 `BillReport` 与原任务 checkpoint。月均按总消费 × 30 ÷ 北京时间实际天数计算；分享 purpose 不授予第三方访问权。
- 根据独立 Spec 复核修复：非法月份与未支持时间不得扩大为全年；类别/明细限制须先由用户选择查看完整报告再取数；成功重放恢复类型化 `BillReport`，保留同一 `report_id`，不重复银行读取或报告生成。
- 半月、多月份、第二年份和月底的 6 个新参数在修复前 **6 failed / 8 passed**，修复后 `3aa83d767a6db10c7bc29c35e19f1794d1d136d2` 的 bills **203 passed**、全后端 **742 passed**。进一步补同比、环比、多了、少了 4 个失败参数后修复为当前 `e604dbc`，bills **207 passed**。前一版本的 742 passed 不当作当前版本的全量证明。
- 独立 Standards 复核当前 `e604dbc`：在 backend 执行 `python -m pytest app/modules/bills/test_report_service.py -q -k unsupported_period`，**18 passed, 16 deselected in 0.16s**。此前提出的“9 月上半月”“9 月下半月”“9 月和 10 月”均进入 `waiting_input`、无银行读取；比较意图同样先澄清。无新公开契约、权限或注册范围扩大，本轴无新增阻断项。
- 最终 [CI 39221814575 / job 117958630688](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/39221814575/job/117958630688) 已 success，根执行者核对原日志：后端 **746 passed in 141.58s**，Mock Bank **14 passed in 0.53s**。该证据对应最终远端 head，不再以 3aa83d7 的 742 项替代最终版本。
- 平台正式装配、生产审批/规划路由、报告真实落库、F21—F24、前端与专业安全审查仍需相应工作线实际验证。模块代码与 CI 完成不关闭本票；等待 Erwin 审查与合入决定。

### 2026-10-19 后续：同步已合入 PR #153 的新主线

- 最新远端 [f4e672e0d177f87b46239aea1e2ca5668f2e347f](https://github.com/DrErwin/hackerthon-bank-agent/commit/f4e672e0d177f87b46239aea1e2ca5668f2e347f) 基于新 main `cd7c91ad80652852bb10fef139c2442d756ef359`，Git 树为 `0e8122a0ec557fd146b5b3aeba161522acaf1b5e`。前序 97441e / CI 39221814575 的 746/14 作为当时版本证据保留。
- 新 [CI 39223073629 / job 117962732134](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/39223073629/job/117962732134) 已 success；根执行者核对日志为后端 **747 passed in 109.86s**，Mock Bank **14 passed in 0.43s**，没有沿用前序 746。
- 后续 [07](07-integration-evidence.md) 在已发布组合及明确注入的评测 runtime 上完成 **7 个报告/导出 HTTP 场景通过**，实际贯通 L03 → 自动报告资源落库 → F21/F22/F23/F24 与银行验证。该 HTTP 层证据归票 07，不更改本票生产模块范围、不代表默认工厂/生产策略已准入，也不将其 87 个请求累加为模块测试数量。

### 2026-10-20 晚 L03 实证结论

Ethan 的 [PR #151](https://github.com/DrErwin/hackerthon-bank-agent/pull/151) 已合入 L03 报告模块。Erwin 的 [平台阶段二 PR #193](https://github.com/DrErwin/hackerthon-bank-agent/pull/193) 已合入，真实 `glm-5.3` 两次独立运行走通报告任务/恢复、`BillReport` 自动落库、F21 查询、F22/F24 普通卡片、验证后敏感 CSV 共18行，且金额与真实种子银行 B08 对账。**本票报告模块完成**，但不代替 L02 安全准入、React 账单页面和整包联合验收。
