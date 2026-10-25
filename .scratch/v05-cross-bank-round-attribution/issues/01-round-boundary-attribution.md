# 01：生日跨轮次边界的真实装配归因

Ticket ID: v05-cross-bank-round-attribution/01

Package: [v05-cross-linkage/packages/06-bank-eval：银行专项验收](../../v05-cross-linkage/packages/06-bank-eval.md)

Spec: [只读归因规格](../spec.md)

Type: 评测

Owner: Erwin

Directory: `evals/mockbank/`

Status: in_review — PR296修复后的组合复验已跑，待本轮两轴审查；原专项保持blocked，296/294均未获本批合入批准。

Accepted by: Erwin（中控授权执行）

Accepted at: 2026-10-25

Blocked by: [PR #296](https://github.com/DrErwin/hackerthon-bank-agent/pull/296)（`v05-cross-platform/14`订单来源门，仍Draft未合入）；本轮原PR294作为依赖Draft，原专项验收不由本票收口。

Source: [PR #290](https://github.com/DrErwin/hackerthon-bank-agent/pull/290) 及 2026-10-25 中控续派；保留其blocked与四项已知失败。

Core scenarios: RA01—RA05，见本规格；关联原XL-B及轮次隔离要求。

## 交付及验证

- 本组装配探针使用独立临时SQLite、真实build_runtime、安全门/执行器、确认/验证、网关与银行，不使用常量允许写回调、不调真实模型；组合中的290裸银行测试allow属于另一层，单列边界，不混为真实安全门证据。
- 核对旧会话/任务、旧授权、缺claim、当前轮次新任务使用旧对象的不同结果。
- 区分真实ASGI测试请求、直接内部端口探针、静态路径检查和未实现入口；不写页面E2E或实际外部HTTP越权已证实。
- 在原归因上复验296的现有规则接线，保留历史失败并将当前测试改为旧订单拒绝与合法订单对照；不修改后端、不裁定银行新政策、不删除290四项strict xfail。
- 子代理独立两轴复核后更新原PR294交中控，不新建重复票/PR，不自行合并、不修改共享跟踪/版本完成事实。

## Delivery record

以下为**首次只读归因历史**（294原head `eb24d739e3c3a431d34f1d164b6aca1a8cfe4470`，尚无296来源门），不得套用为修复后当前行为。当前结论及验证见文末。

- 基线 `9a479ea4414635772fdb723c02b0fc70b76a1a55`；分支 `codex/v05-bank-round-attribution-02`；独立worktree `C:/Users/57652/.codex/worktrees/v05-bank-round-attribution-02/hackerthon-bank-agent`。
- [当时归因报告](https://github.com/DrErwin/hackerthon-bank-agent/blob/eb24d739e3c3a431d34f1d164b6aca1a8cfe4470/evals/mockbank/round-attribution.md)及[当时探针](https://github.com/DrErwin/hackerthon-bank-agent/blob/eb24d739e3c3a431d34f1d164b6aca1a8cfe4470/evals/mockbank/test_birthday_round_attribution.py)，[当时JUnit](../../../evals/mockbank/evidence/round-scope-history/pr294-eb24d73-before296.xml)。当时3 passed in 14.28s，仅说明首次归因断言符合当时行为。
- 旧API身份/任务受阻、真实写claim有效、旧上下文先STALE_ROUND；D2内部端口经过真实确认/验证仍可付款已知D1订单。未证明页面/正常HTTP可注入旧编号；不新增政策，最小平台资源核对票仅建议。
- 原PR290与四项已知失败未改。归因通过不代表原银行专项验收通过。
- 独立Standards/Spec子代理复核均0项必须修复，分别复跑3 passed；轻微模型调用措辞建议已修正。相关原用例4 passed, 32 deselected in 18.50s。
- [PR #294](https://github.com/DrErwin/hackerthon-bank-agent/pull/294) 已提交并附执行对话，交中控排队，未自行合并。代码提交`db66250`；之后仅事实/措辞/交付记录。rebase到`fd6cd703846a9614e32cff1434fdfe343fdd18c8`只引入主线文档及其他评测文档，运行实现未变。
- CI实查head `74e9471` 的[Repository checks](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/40168942779/job/121095667265) failure且job未启动，GitHub原因为账号近期付款失败或消费额度需提高；属于Actions环境阻塞，不记CI绿。中控合入前复核最终head。现CI显式银行命令仍仅旧评测文件，本轮3项由上面的本地命令留证。
- 不以模型替身/ASGI检查冒充真实模型/外部TCP/页面E2E，不重复跑无关全后端/模型评测。只读归因已交；平台最小修复票仍是建议，未代替中控正式分派，未新增银行轮次政策。

## 2026-10-25 中控续派：296修复后实际组合复验

- 正式沿用本票与PR294，转Draft并声明Depends on PR296；仅本组材料及evals/mockbank改动。平台14实现本票不接管。
- main固定 `0930d6be59c728b9dc0ef4c4ef0b5430da12943e`；296固定 `b41ef64df525d71a29e0a6c3c8f49f8a20942e01`；294原来源 `eb24d739e3c3a431d34f1d164b6aca1a8cfe4470`；290固定 `e9f2793bb29ec90816695ad48f8d855b16e5e9b4`。main已含289；未使用296提供方1599项作为本票全量。
- 组合worktree `C:/Users/57652/.codex/worktrees/v05-bank-294-296-verify/hackerthon-bank-agent`，本地组合HEAD `577f560199a449ff9df20d6017e65025d7ad7cb3`：main合原294、再合296；之后仅替换本组测试、取入290原评测单文件。backend相对组合HEAD零工作区修改。
- 原294旧断言在296组合 **1 failed, 2 passed in 16.11s**，因为实际BLOCK而非原来要求的确认；保留历史XML和旧报告Git引用，修正当前回归断言。新回归在main093无296时反向 **1 failed, 2 passed in 15.18s**，真实检出旧门缺失。
- 新本组回归组合单跑 **3 passed in 10.39s**；定向本组+290银行+296来源门+生日装配 **53 passed, 4 xfailed in 74.96s**。4xfail仍是290裸银行测试allow下对象接口边界，不计通过、不据此断言产品越权。真实门下拒绝旧订单，合法本任务订单只付199一次。
- 发布分支按仓库依赖规则叠在296固定head上，仅保留294自身评测/材料；`b41ef64...HEAD`没有backend差异。该发布stack另跑本组 **3 passed in 10.42s**，[发布stack原始记录](../../../evals/mockbank/round-attribution-stack-results.xml)。其父基线与含main093的完整验证组合分别记录，不混称相同Git HEAD；更新测试blob均为 `c6ca4be9d360f73f00ada3c29efb8d3eaa061285`。
- [当前完整报告](../../../evals/mockbank/round-attribution.md)、[组合JUnit](../../../evals/mockbank/round-attribution-combined-results.xml)及[历史证据](../../../evals/mockbank/evidence/round-scope-history/pr294-eb24d73-before296.xml)可核对精确来源和层级。没有全后端/真实模型/外部TCP/页面E2E/共享演示数据操作。
- 本轮独立Spec/真实性审查0项必须项，验证组合复跑3 passed in 9.82s。Standards审查0项代码必须项、1项历史证据链接必须项及失败XML行尾空白工具检查；已改为固定历史链接，失败XML仅CRLF→LF（解析后的XML内容/元数据严格相同），待只读复核。Standards独立组合复跑3 passed in 10.21s。
- PR294仍未合并，原专项及安全/页面E2E/真人接受不关闭，原五PR合入批准不扩用。
