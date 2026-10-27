# 演示风险数据说明

Status: implemented_pending_review
Owner: Erwin（v0.5）；执行 frontend_acceptance 子代理
Accepted by: Erwin，通过 2026-10-27 非比赛资料授权、养老金两笔限定演示 profile 批准及中控明确分派
Accepted at: 2026-10-27
Package: [v05-cross-linkage/packages/04-frontend：页面体验](../v05-cross-linkage/packages/04-frontend.md)，本轮演示边界说明后继
Directory: frontend/

## 问题与最小方案

在 main `c760f0d0` 检查：真实 API 的 `originLabel` 返回空，TopBar 只有 stub/contract-demo 显示演示资料说明；现有用户页面仅标明模拟人脸，没有说明部分风险判断采用预设事实。真实 API/模型连接可能因此被误认为风险输入也已全部真实核实。

RD01：复用顶栏下现有说明区域，真实 API 用户页显示“演示数据：部分风险判断采用预设场景，转账仍需确认和验证。”。文字在对话滚动区外，既有字号与换行样式照用；不增加技术标签或新布局。

RD02：stub/contract-demo 原说明保留；不增加接口、配置或风险判定，不放宽危险/新收款人/确认验证及未知暂停，不宣称真实风控全完成。

## 验证与边界

低影响静态文案不写逐字镜像测试。运行已有 shell/对话交互及真实数据源边界检查、类型检查和真实 API/contract-demo 两构建；明确是本次固定代码的回归，既有122/136基线不当新结果引用。构建和代码位置核对不等同于真实浏览器可见性验收。

CUA 先前因无法可靠识别 Windows URL 安全停止，用户手动恢复回执仍缺。本票不重试或更换浏览器/Playwright 通道；200%、完整读屏、真机和截图仍阻塞。仅 frontend 及本组过程材料，独立 PR 交根代理两轴，不自合并、不写比赛资料。

## 本次实际结果（2026-10-27）

- `npx tsc -b`：通过。
- `npm test -- src/shell/shell.test.tsx src/shell/agent-conversation.test.tsx src/shell/api/realDataSource.test.ts`：3 文件 / 20 passed / 30.17s。本次运行既有交互与数据源回归，未增加文案镜像测试；不以此声称新增真实风险检测或真实页面验收。
- `npm run build` 及 `VITE_API_MODE=contract-demo npm run build`：均通过；既有大于500kB chunk提醒保留。
- `git diff --check`：通过。运行代码仅 TopBar 增加真实 API 条件下的一条既有样式说明，其他模式原文案无差异。

独立 Standards/Spec 两轴及合入待中控；实际200%、完整读屏、真机和截图仍阻塞。
