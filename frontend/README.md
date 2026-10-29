# frontend —— 用户前端（React）

## 当前设计入口（2026-10-29）

当前 React 前台已替换简易主入口，并接入三个生活目标。10-29 页面完成新 500 元转账及刷新无重复扣款核对，减支原计划经登录恢复后办结；生日/P01 完整页面和聊天“继续”新接缝复验仍待。[最新页面、截图与限制](../.scratch/v05-control/ui-walkthrough-2026-10-29/walkthrough.md)是当前取证入口，早期记录按各自当时状态阅读。

前端固定树已有 136 项、类型检查与真实 API/契约演示两种构建证据，见[集成记录](../.scratch/v05-control/integration-2026-10-28.md)。大字、390 像素视口及局部键盘检查已有证据；真实 200% 缩放、完整读屏、真机和最终体验接受仍待。v0.5 剩余执行统一由 Erwin 承担，长期归属不变。

- [设计系统](DESIGN.md)：对话驱动、手机优先，shadcn/ui + Radix / Vaul、Tailwind 4、Lucide、Sonner。
- [全业务交互改造方案](交互改造方案-v0.2.md)：现状、目标与逐项替换顺序。
- `npm run dev` 后打开 `/v04/design-system`：实际安装组件的可点击体验页，使用虚构示例资料；`/design-system-preview.html` 显示手机预览。
- `/conversation-preview.html`：当前前台的手机预览，复用实际 React 界面。以 `VITE_API_MODE=contract-demo` 启动可体验转账、查询穿插与修改；固定回复仅用于交互演示。真实 Agent 仍经既有 API 接入。
- 当前用户前台已统一接入：对话与办理记录、账户/收款人搜索、账单月份与分类、订阅退订、生活安排、确认验证、结果回执与恢复。资料、点选和文字办理共用原任务；大字偏好保留到下次打开。
- shadcn 源码位于 `src/components/ui/`，由官方 CLI 的 `new-york` 注册表加入，已调整默认字号/高度、中文关闭、进度语义和浅色提示。后续 `add` 先看差异，保留这些适老化调整。Tailwind 不导入 preflight；变量限定用户前台、组件体验页和 portal，历史页面沿用原样式。

2026-10-26 交付历史及独立检查见 [frontend-design-system/03 验证记录](../.scratch/frontend-design-system/verification-03.md)及[浏览器报告](../.scratch/frontend-design-system/e2e-03.md)。当时真实转账遇安全事实覆盖暂停；后续限定演示组合已完成页面转账，缺覆盖组合仍暂停，#160 仍未收口。契约演示、真实 API/模型和最终用户接受分别记录。

真实接口体验可使用 `scripts/run-ux-backend.py`：先设置 `BANK_LOCAL_CONFIG` 指向本机已有私密演示配置，`PYTHONPATH` 指向本仓库 `backend/`，用后端虚拟环境运行脚本。它在临时目录创建独立数据库，监听 `5191`。前端设置 `VITE_API_MODE=real-api`、`VITE_API_PROXY_TARGET=http://127.0.0.1:5191`，运行 `npm run dev -- --host 127.0.0.1 --port 5190`。凭证留在本机后端配置中。

2026-10-22 Demo 修复历史（[bank-e2e-remediation/02](../.scratch/bank-e2e-remediation/issues/02-interactive-cards.md)，Issue #227）：补充卡接入金额、收款人线索、付款账户及商户。确认阶段修改调用同一任务的草稿入口，旧确认只读、新确认须重新批准。该时点自由语言修改/跨任务推断尚未接入；后续实现与当前证据以 10-26 验证记录为准。订阅验证码动作声明由票 03 修正，前端不能自行扩大后台允许动作。

等待状态保持到回复/错误，真实处理错误如实展示；可重试请求保留原请求编号。语音按钮明确为固定文字示例，不采集声音；真实识别和播报本轮未接入。组件测试与真实 React/模型联调分开记录，不据此声称全部 E2E 修复或安全验收。

归属：梁爽负责，六水协助（2026-09-25 Erwin 确认）。

放什么：对话界面、进度与等待展示、敏感操作确认（确认单 / 验证码 / 人脸三个安全交互）、结果与报告卡片、结果待核实的只读查询入口、适老化交互（大字 / 高对比 / 语音播报 P1）。接口面 = [契约大纲](../docs/contracts/公共契约-2026-09-23.md)第 6 章接口与六条链路（聊天 / 确认 / 验证 / 报告 / 事件与恢复 / 待核实结果查询，§6.2）。

2026-10-01阶段安排：梁爽、六水本阶段只交普通转账关键流程原型图；Erwin临时做简易前端用于真实接口联调，10-10前可联调、10-12前阶段验收。后续完整前端仍采用React + Vite + TypeScript，类型复用公共契约（架构§8），不为简易前端另定业务或安全规则。

边界：**前端只展示和收集用户动作，不做权限判定**（安全底线，见 [principles/02](../docs/principles/02-security-platform.md)）；登录口径 = 演示固定用户 + 自动登录（契约 6.3）。

历史节点：原型 10-06 入库，五类补图 10-12 走查通过；简易前端与真实联调已完成；[完整前端工作线](../.scratch/frontend-complete/packages/01-v04-complete-frontend.md)随后替换主入口并于 10-21 获 PM 接受，新版对话前台于 10-27 合入。当前联动页面与真实验收按[项目跟踪](../docs/01-项目跟踪.md)继续。

## 本目录现有交付物

| 文件 | 来源 | 状态 |
|---|---|---|
| [前端-设计规范-v0.1.md](前端-设计规范-v0.1.md) · [前端-用户体验规范-v0.1.md](前端-用户体验规范-v0.1.md) | 提交 `31de4c9`（2026-10-06） | 已交付；两份规范末尾均带「待确认（回『行』或『改 X』）」清单，走查后迭代 |
| [转账-交互原型-v0.1.html](转账-交互原型-v0.1.html) | [PR #77](https://github.com/DrErwin/hackerthon-bank-agent/pull/77)（2026-10-06）；v0.2 已走查通过（PR [#106](https://github.com/DrErwin/hackerthon-bank-agent/pull/106)，2026-10-12） | v0.2 已补候选、等待、模拟人脸、刷新恢复和修改交互；Erwin 按图走查通过 |
| `src/` 当前 React 前台 | 完整前端 #199/#201，新版前台 #318/#319/#320，后续提示修补 #348 | 已替换简易主入口；实际页面范围见本页顶部 |

**原型 v0.2 已走查通过（2026-10-12）**：收款人候选、等待态、模拟人脸核验、刷新恢复和修改画面已在现有 HTML 原型补齐；390×844 视口下候选 / 修改 / 验证码 / 模拟人脸 / 等待 / 结果路径可点击走通，刷新不会自动重新提交，用户页没有人脸结果按钮。Erwin 在隔离工作区实机按图走查通过并合入（[PR #106](https://github.com/DrErwin/hackerthon-bank-agent/pull/106)），原型工作线据此收口、完整前端按[交付包 01](../.scratch/frontend-complete/packages/01-v04-complete-frontend.md)开工（底盘与转账 stub 先行）。以上仍是本地原型验证，不代表真实 API 联调；`?mode=admin` 只表达演示端分离，不构成真实鉴权。

历史交付见[v0.3 完成情况](../docs/versions/v0.3.0/completion.md)和[v0.4 完成情况](../docs/versions/v0.4.0/completion.md)；当前状态与剩余见[v0.5 完成情况](../docs/versions/v0.5.0/completion.md)。
