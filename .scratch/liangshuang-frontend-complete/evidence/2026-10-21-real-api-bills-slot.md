# 票 04 账单插槽真实接口联调证据（2026-10-21）

- 票：[liangshuang-frontend-complete/04：账单业务插槽](https://github.com/DrErwin/hackerthon-bank-agent/blob/main/.scratch/liangshuang-frontend-complete/issues/04-bills-slot.md)
- PR：[#199](https://github.com/DrErwin/hackerthon-bank-agent/pull/199)「feat(frontend): 账单插槽展示汇总、明细、异常和报告」，作者梁爽；本证据对应 rebase 到最新 main 后的分支 head：`f87b631`（作者提交）+ `6a9d90a`（审查修复，AI 代修）
- 执行：AI 实施者（Lead 会话）代执行 · **AI 代填留痕，非真人 UI 走查、非 Ringo 本人安全审查**
- 结论：**真实接口联调通过（5 场景 / 94 项断言全通过 / VERDICT=PASS）**；真实 local-demo 后端 + 真实 GLM（Coding Plan）+ 模拟银行，**不是 contract-demo，也不是 stub**
- 采集时间：2026-10-21 00:04–00:05（Asia/Taipei）

## 1. 环境

| 项 | 值 |
|---|---|
| 前端 | PR #199 worktree `D:\hb-worktrees\frontend-bills`，Vite dev `127.0.0.1:5173`，`VITE_API_MODE=real-api`、`VITE_API_PROXY_TARGET=http://127.0.0.1:8000` |
| 后端 | 仓库 main `9b27d5b`（后端不属本票改动），`uvicorn app.agent_platform.local_demo:create_local_app --factory --port 8000`，配置仓库根 `.env.local-demo.json` |
| 模型 | 智谱 `glm-5.3`，**Coding Plan 入口** `https://open.bigmodel.cn/api/coding/paas/v4/`（普通 API 入口未切换；配置/额度错误会明确失败，不自动换测试模型） |
| 银行 | 模拟银行受控组合，用户 `U1`（账户 A1/A5） |
| 浏览器 | Microsoft Edge（系统安装，headless），视口 1280×900 |
| 驱动 | `puppeteer-core`（`npm i --no-save`，不写入 `package.json`） |

## 2. 合入前本地检查

- rebase：`git rebase origin/main`（main `9b27d5b`）零冲突；`backend/app/contracts` 自旧 base `3d1ea90` 以来无变化，`frontend/src/api.generated.ts` 无需重新生成。
- `npm ci`：通过。
- `npm test`：**5 文件 / 38 tests passed**（含本 PR 新增 `billsSlot.test.tsx` 4 项；审查修复后复跑仍 38 passed）。
- `npm run build`（`tsc -b && vite build`）：通过，38 modules，产物 `343.97 kB`。
- 前端 test/build 不在仓库 CI 覆盖范围内，按 `frontend/LOCAL-DEV.md` 本地执行并在此记录。

## 3. 审查修复（提交 `6a9d90a`，AI 代修）

双轴 AI 审查（非真人）结论「有条件可合」。按 PM 2026-10-21 00:00 决定处置：

- **已修**：① 交易行按 `nature` 显示 消费/退款/转账/利息（原先退款会显示成「收入」）；② 数据不足的 `RuleCheck.reason` 由后端机器码映射为中文，未知统一「这次没能核对」，删除「银行没有返回原因」的错误归因；③ 有符号金额统一 `-¥300.00` 形式。
- **未采纳（PM 决定）**：审查第 1 项「异常卡在仅有数据不足时仍显示『没有发现需要留意的交易』+ 成功色」保留现状，记入票 04 遗留清单；后端 message 仍带「部分规则数据不足…不能据此确认正常或盗刷」的说明。
- 其余低优先项（明细渠道字段、报告导出入口、演示模式示例句、适老化精简、载荷判别字段等）记入票 04 Comments 遗留清单，不阻塞本 PR。

## 4. 真实栈与场景

启动：`pwsh tools/start_local_dev.ps1 -SkipNpmInstall`（或分别启动后端 8000 与前端 5173）。所有场景走 `/v04` 真实接口；页面**无 contract-demo 标记、无演示数据横幅/角标**，顶栏显示「演示用户 · 已连接」。

每个场景在独立新线程中执行；证据脚本把**同一任务的 API 返回 payload** 与页面渲染逐字段比对。

| # | 用户输入 | 真实交互路径 | 页面结果（与 API payload 一致） | 截图 |
|---|---|---|---|---|
| 1 | 这个月花了多少 | 询问账户范围 → 选「所有本人账户」 | 消费汇总：净额 ¥235.00；消费支出 ¥235.00、退款 ¥0.00、转出 ¥5002.00、转入 ¥8200.00；笔数 19；覆盖账户 2；7 个分类（转账 ¥5002.00、购物 ¥98.00 · 41.70%、餐饮 ¥73.00 · 31.06%、医疗 ¥62.00 · 26.38%、交通 ¥2.00 · 0.85%、居住/其他 ¥0.00）；数据时间 2026/10/21 00:04 | [01-summary.png](2026-10-21-real-api-bills-slot/01-summary.png) |
| 2 | 看看这个月的餐饮明细 | 选「所有本人账户」 | 餐饮明细 2 笔：楼下面馆 ¥28.00（消费、餐饮、午餐、2026/10/08 12:20）、社区食堂 ¥45.00（消费、餐饮、晚餐、2026/10/17 18:10）；商户名原样展示（未被打码），数据时间 2026/10/21 00:04 | [02-detail-dining.png](2026-10-21-real-api-bills-slot/02-detail-dining.png) |
| 3 | 看看这个月的转账明细 | 选「所有本人账户」 | 转账明细 12 笔；对端为 `王** · ****0002` 的行原样展示后台打码账号，条数/金额/类型/分类/时间逐行与 payload 一致 | [03-detail-transfer.png](2026-10-21-real-api-bills-slot/03-detail-transfer.png) |
| 4 | 这笔钱我不认识，是不是扣错了 | 确认查询范围「本月」→「列出原范围流水」→ 选「所有本人账户」→ 从 19 笔候选中选第 18 笔（2026-10-20 01:24 王\*\* 500.00 元） | 办理结果「有账单提示」：定位到所选交易（`¥500.00 · 转账 · 2026/10/20 01:24 · ****0002 · 转账`）；**真实命中规则 3**（夜间交易）：「该交易发生在北京时间夜间时段，请核对是否本人操作。」+ 建议 + 相关交易号；规则 1 数据不足显示中文原因「本人转账关系未确认」；规则 2/4 已核对未命中（不渲染）；整块 **0 个可操作按钮**，只提示、不代用户执行、不编造金额 | [04-anomaly.png](2026-10-21-real-api-bills-slot/04-anomaly.png) |
| 5 | 给我出一份这个月的账单 | 选「所有本人账户」 | 账单报告（非「办理结果」卡）：统计范围 2026/10/01–2026/11/01；消费净额 ¥235.00；支出/退款/转出/转入/笔数/覆盖账户/7 分类同场景 1；月均消费 ¥335.71、统计天数 21、月均口径「按统计天数折算，每月30天；不预测未来实际支出」、报告生成时间 2026/10/21 00:05；口播摘要「本次共查询到19笔交易；消费支出235元00分，退款0元00分，净消费235元00分。」；**报告卡内无任何原始明细/商户名/交易号**，全程无「演示数据」字样 | [05-report.png](2026-10-21-real-api-bills-slot/05-report.png) |

## 5. 断言与 API 观测

- 断言：5 场景 **94 项检查全部 true**（`walkthrough.json.checks`）：任务 succeeded、卡片标题、金额/笔数/分类/占比/时间/范围逐字段与 payload 比对、商户名原样、打码账号原样、异常命中证据与建议、数据不足中文原因、无操作按钮、无演示标记、报告不含原始明细、报告口播与生成时间。
- API：23 次 `/api/v1` 调用 = **18×200 + 5×202**（消息受理）；无预期外 4xx/5xx，无控制台错误。
- 机器可读证据：[walkthrough.json](2026-10-21-real-api-bills-slot/walkthrough.json)；复跑脚本：[walkthrough.cjs](2026-10-21-real-api-bills-slot/walkthrough.cjs)。

复跑方式（本机）：后端按 `backend/app/agent_platform/LOCAL-DEV.md` 起 8000，前端 worktree 内 `npm run dev`（5173，real-api），然后

```powershell
$env:NODE_PATH = 'D:\hb-worktrees\frontend-bills\frontend\node_modules'
node .scratch\liangshuang-frontend-complete\evidence\2026-10-21-real-api-bills-slot\walkthrough.cjs all
```

## 6. 覆盖与不覆盖

- 覆盖：票 04 交付清单的四类展示（汇总/明细/异常/报告）及真实交互路径（账户选择、查询范围、候选流水选择）。
- 本机演示数据随运行累积（含 2026-10-20 01:24/01:30 的演示任务流水），上述金额为运行时刻真实数据；断言是与同一 payload 逐字段比对，不依赖固定金额。
- L02 演示事实缺可信亲属状态（`trusted_family_status_required`），规则 1 按真实返回显示「数据不足 · 本人转账关系未确认」；前端只做展示映射、不补造理由。**可读性/口径改进（如后端直接返回中文原因）建议由账单/平台侧另行登记，不阻断本票。**
- 不覆盖：明细导出（本 PR 未实现，不在票 04 交付清单）、501/502/600 转账双因子与终止路径（票 03 已有证据）、390×844 移动端适老化走查与替换主入口（票 05）、生产部署与真实银行。
- 本证据为 AI 代执行，不代表 Ringo 本人安全/交互审查；PR #199 未新增或改动确认/验证交互（复用票 03 已走查底盘），Ringo 审查与 PM 验收分别记录、互不替代。

## 7. 证据文件（本目录 = `.scratch/liangshuang-frontend-complete/evidence/2026-10-21-real-api-bills-slot/`）

| 文件 | 内容 |
|---|---|
| `01-summary.png` | 汇总卡（真实接口） |
| `02-detail-dining.png` | 餐饮明细（商户名未打码） |
| `03-detail-transfer.png` | 转账明细（`****0002` 后台打码原样展示） |
| `04-anomaly.png` | 异常提示：夜间规则命中 + 数据不足中文原因，无操作按钮 |
| `05-report.png` | 账单报告（无原始明细、无演示字样） |
| `walkthrough.cjs` | 可复跑脚本（Edge headless + puppeteer-core，逐字段断言） |
| `walkthrough.json` | 机器可读结果（场景、payload、94 项 checks、API 调用、VERDICT=PASS） |
