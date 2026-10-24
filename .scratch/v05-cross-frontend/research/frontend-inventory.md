# 前端现状盘点：为「跨场景联动（减支 / 养老金月度安排 / 生日）」页面设计做准备

Status: 只读盘点完成（未改业务代码、未提交、未启动服务器、未跑会改文件的命令）
盘点日期：2026-10-25
基线：开始时 `git log -1` = `232123f docs: 登记联动页面包04领取并细化两票`
盘点方式：`git status` / `git log` / 读文件 / grep。
产出位置：本文件（新增，未跟踪）；`frontend/` 源码在盘点期间未改动（`git status` 无 `frontend/src` 变更）。

> **工作区并发说明（如实）**：盘点期间同一工作区有并发写入——开始时 `git status` 无未跟踪文件、HEAD 为 `232123f`；结束时 HEAD 前进到 `b071408 docs: 登记 v05-cross-frontend/01 执行对话接手`，并出现非本报告产出的未跟踪文件 `.scratch/v05-cross-frontend/page-plan-01.md`（票 01 页面方案）与 `frontend/联动-交互原型-v0.1.html`（原型）。本报告所有 `frontend/src` 证据读自该目录在 `232123f` 的内容，且盘点全程 `git status` 未出现 `frontend/src` 变更。

## 0. 一句话结论

现有 shell（v0.4）已经是一套"任务时间线 + 卡片编排 + 插槽映射 + 幂等数据源"的成熟底盘，**确认 / 验证 / 等待 / 结果 / 待核实 / 恢复 / 父子卡片**全部有可复用实现；但**联动（cross）在前端是完全空白的**：无类型、无插槽、无接口调用、无任何 budget / birthday / pension 文案占位。实现联动页面的工作主要是"新增一层总览 + 子项绑定"，而不是重做交互。

---

## 1. 页面与路由

### 1.1 主入口与路由表

唯一入口是 `frontend/src/main.tsx:4-10`（挂 `App`，全局引入 `styles.css`）。

`frontend/src/App.tsx:83-91` 用 `window.location.pathname` 做**手写路由**（没有 react-router）：

| 路径 | 渲染 | 证据 |
|---|---|---|
| `/legacy`、`/legacy/*` | `UserPage()`（v0.3 简易前端，含 `TaskCard`） | `App.tsx:87` |
| `/v04`、`/v04/*` | `ShellApp` | `App.tsx:88` |
| `/admin` | `AdminPage`（简易前端的管理页） | `App.tsx:89` |
| 其他（含 `/`） | `ShellApp`（**当前主入口**） | `App.tsx:90` |

`App.tsx:85-86` 注释明确了这条替换关系："正式前端（完整 App）承接 `/`；简易前端保留在 `/legacy` 作回滚依据；管理页 `/admin` 与旧路径 `/v04` 保持不变"。

`ShellApp` 内部再分一次（`frontend/src/shell/ShellApp.tsx:21-24`）：

| 路径 | 渲染 |
|---|---|
| `/v04/admin*` | `AdminDemoPage`（stub 演示管理端） |
| `/v04/gallery*` | `GalleryPage`（组件状态目录） |
| 其余 | `AssistantPage`（聊天主页面） |

数据源与插槽在 `ShellApp.tsx:17-20` 一次性构造：`createDemoBackend()`、`createRealDataSource()`、`createSlotRegistry([transferSlot, billsSlot])`；`ShellApp.tsx:24` 按 `shellUsesContractDemo()`（`ShellApp.tsx:13-15`，判断 `API_MODE === "contract-demo"`）在 stub 用户源与真实 API 源之间二选一。

> 结论：**路由是路径字符串分支，不是组件路由**。新增"联动结果页"如果不做新路径，最自然的是留在时间线里（见 §7）；若要做独立页面，必须在 `ShellApp.tsx:21-24` 增加 `path.startsWith(...)` 分支。

### 1.2 页面骨架

**A. `AssistantPage`（主页面，`shell/AssistantPage.tsx:67-136`）**

单列聊天壳，没有侧栏：

1. 跳转链接 `.sh-skip`（`:69`）
2. `TopBar`（品牌 + 连接状态，`:70`；实现在 `components/Chrome.tsx:7-39`）
3. `ExpiredBanner`（`:71`）
4. 断线 `Notice`（`:72-73`）
5. **读屏汇总** `sr-only role="status" aria-live="polite" aria-atomic`（`:74-76`）
6. `div.sh-body`（滚动容器，`:77-82`）→ `.sh-body-inner` → `main.sh-main#sh-main`（`:84`）→ `.sh-timeline`（`:85`）
7. 时间线内容：欢迎气泡 + 快捷按钮（`:86-96`）、`booting` 提示（`:97`）、`timeline.map` → `MessageBubble` / `TaskRecord`+`TaskBlock`（`:98-106`）、等待回复（`:107`）、`pageError`（`:108`）、`pageNotice`（`:109`）
8. "回到最新消息"浮层（`:115`）
9. `SafetyRail` 办理须知（`:116`，实现 `Chrome.tsx:171-184`）
10. "继续办理"多任务导航条 `.sh-pending-nav`（`:117-128`）
11. `Composer` 底部输入（`:129-134`，实现 `Chrome.tsx:61-157`）

**B. `GalleryPage`（状态目录，`shell/GalleryPage.tsx:1-96`）**

- 文件头注释即定位："Static walk-through of every shell card state, for design review and accessibility checks. All values are fixtures; nothing here talks to a data source."（`:1-2`）
- 结构：`TopBar`（`:46`）+ `main.sh-gallery-main`（`:47`）+ 8 个 `Section`（`:48-92`）：消息与等待、补充信息、确认单、验证码+模拟人脸（5 态）、结果与报告、待核实与刷新恢复、错误与异常。
- `Section` 是本地小组件（`:34-41`），不可复用。
- **这是新页面"先走查版式"最合适的落点**：ticket 01 要求先提交版式走查（`.scratch/v05-cross-frontend/issues/01-plan-and-child-interactions.md:49`），把联动状态加进 Gallery 可以在不接后端的情况下被走查。

**C. `AdminDemoPage`（`shell/AdminDemoPage.tsx:9-143`）**

独立管理端：顶栏（`:90-96`）+ 提示 `Notice`（`:98-100`）+ 人脸作答卡（`:109-123`）+ 其他演示操作（`:124-136`）。用 `setInterval(refresh, 1000)` 轮询（`:35`）。

**D. `AdminPage`（简易前端管理页，`AdminPage.tsx:21-249`）**

管理员登录（`:147-177`）+ 模拟人脸（`:193-212`）+ 只读审计时间线（`:214-245`）。只在 `/admin` 使用。

**E. `UserPage`（`/legacy`，`App.tsx:93-467`）**

三栏布局：`header.topbar`（`:332-344`）+ `aside.thread-rail` 对话列表（`:347-372`）+ `main.conversation-column`（`:374-445`）+ `aside.help-rail`（`:447-463`）。栅格定义在 `styles.css:92`（`232px minmax(440px,1fr) 244px`）。

> **重要差异**：shell 主页面**没有侧栏**。`shell.css:202-208` 里有一套 `@media (min-width: 1100px) .sh-rail {...}` 的桌面右栏样式，但**全仓库没有任何 tsx 使用 `sh-rail`**（grep 只命中 `shell.css`）——属于死 CSS。新增联动页面不要假设有侧栏可放总览。

### 1.3 脚本与测试框架

`frontend/package.json:6-12`：

| 脚本 | 内容 |
|---|---|
| `dev` | `vite` |
| `build` | `tsc -b && vite build` |
| `generate:contracts` | `python scripts/generate_contract_schema.py && json2ts --unknownAny --unreachableDefinitions -i .contract-schema.json -o src/api.generated.ts` |
| `test` | `vitest run --environment jsdom` |
| `preview` | `vite preview` |

- **没有 `lint` 脚本**（`package.json` 全量 29 行内无 lint 相关脚本或 eslint 依赖）。
- 测试框架：**vitest 5.0.3 + jsdom 30.1.1 + @testing-library/react 16.3.3 + @testing-library/dom 10.4.2**（`package.json:17-28`）；**不是 jest**。
- 没有 `vitest.config.ts`（`frontend/` 下只有 `vite.config.ts`，且无 `test` 字段），jsdom 环境靠命令行参数；**没有 setupFiles**，各测试文件自行打 `HTMLDialogElement.prototype.showModal/close` 补丁（例：`shell/shell.test.tsx:57-58`）。
- `vite.config.ts:9-20`：dev 固定 `127.0.0.1:5173`、`strictPort`，`/api` 代理到 `VITE_API_PROXY_TARGET`（默认 `http://127.0.0.1:8000`）。
- TS：`tsconfig.json:15-18` `strict: true`、`noUnusedLocals`、`noUnusedParameters`、`noFallthroughCasesInSwitch`；`verbatimModuleSyntax` 在 `:12`。
- `index.html:5` viewport 为 `width=device-width, initial-scale=1.0`（未禁用缩放，200% 缩放可用）。

---

## 2. 卡片与交互组件

### 2.1 `frontend/src/TaskCard.tsx`（旧前端单卡，669 行）

- 职责：v0.3 简易前端的**自包含**任务卡，一个文件包办补充信息 / 确认单 / 验证码 / 模拟人脸 / 收款资料 / 取消 / 查询 / 恢复 / 银行结果。
- 数据来源：**直接 import `get`/`post`**（`TaskCard.tsx:3`），不经过 `ShellDataSource` 与 `useConversation`，与 shell 无共享逻辑。
- 接收形状：`TaskCardProps { task: TaskView; onTask; onRefresh; onError; onSessionExpired; onModifyDraft }`（`TaskCard.tsx:15-22`）。
- 渲染状态：`statusLabel()` 覆盖 9 种（`:36-49`）、`statusClass()` 4 色（`:51-56`）、补充信息面板（`:394-495`）、确认单列表（`:497-540`）、验证记录列表（`:546-588`）、余额不足卡（`:594-603`）、反诈高风险卡（`:605-611`）、银行结果（`:616-633`）、取消/查询/恢复（`:636-658`）、重试沿用 request_id（`:660-665`）。
- 使用范围：仅 `/legacy`（`App.tsx:87`、`App.tsx:405-417`）。
- 可复用价值：**文案与话术**（"聊天里说「确认」不会批准任何资金操作"`:503`、余额不足给下一步`:594-602`、高风险"不提供继续办理入口"`:609`），**结构不建议复用**（与 shell 的 Card/TaskBlock 重复且更旧）。

### 2.2 `shell/components/TaskBlock.tsx`（245 行）— 单个任务的卡片编排器（shell 核心）

- 输入（`:25-31`）：`{ envelope: TaskEnvelope; slot: BusinessSlot; origin: DataOrigin; conversation: Conversation; renderChild?: (id)=>ReactNode }`。
- 内部推导：
  - `busy` / `gated`（`bootRecovery.has(task_id) || task.recovery_required`）（`:34-39`）
  - `guided`（转账草稿引导开关，`:36`）
  - **`displayTask` 沿 `refresh_query`/`bill_range` 子任务向下钻取**（`:43-52`）
  - `transferTargets`（可被"用这张卡付款"的目标任务，`:54-58`）
  - `links` / `activeChildren`（父→子卡片关系，`:59-61`）
- 渲染状态：
  - 恢复门控 → 只渲染 `RecoveryCard`（`:63-81`）
  - `report` / `result` 由 slot 映射（`:83-86`）
  - 历史交互按 `history[task_id]` 逐条渲染：input → `InputCard`、confirmation → `ConfirmationCard`、verification → `VerificationCard`；**当前项直接展开，过去项折叠进 `<details className="sh-past-step">`**（`:109-175`）
  - `running` → `WaitingCard`（`:177`）；`needs_attention` → `NeedsAttentionCard`（`:178-187`）
  - 报告卡 / 结果卡（`:188-189`）
  - `BillDetailsCard` / `BusinessCards` / `BillCardActions`（`:190-206`）
  - 下钻后的"上次查询记录"折叠（`:207-220`）、未成功的 refresh 子任务（`:221-222`）
  - 错误 `Notice`（`:223-228`）、`cancel_requested`（`:229`）、`taskErrors`（`:230-238`）
  - "查看最新余额"（`:239`）、"取消这次办理"（`:240-242`）
- 可复用点：**所有业务卡片的唯一装配处**；新增联动总览最自然的做法是与 `BillDetailsCard`（`:190`）同级插入一个 `CrossPlanCard`。
- 限制：`BusinessSlot` 只能产出 `DisplayField[]` / `ResultView` / `ReportView`（`slots.ts:18-22`），**不能返回自定义 JSX**；因此联动总览若要自定义版式，必须像 `BillDetailsCard` 一样在 `TaskBlock` 内硬接（或扩展 `BusinessSlot` 增加 `card?: (task, ctx) => ReactNode`）。

### 2.3 `shell/components/BusinessCards.tsx`（226 行）— 账户 / 收款人 / 订阅 / 账单

- `businessPayload()`（`:33-40`）：按 `accounts` / `payees` / `action:list|cancel` 窄化 `task.data`（模块无关）。
- `ActionButton`（`:42-72`）：**父卡片一行 → 触发 `onAction(selection)` → 拿到 child task id → 内联展开子卡**；带 `aria-expanded` / `aria-controls` / `useId`（`:64`）、焦点恢复（`:57-62`）。
- `BusinessCards`（`:74-147`）：账户列表（`:85-96`）、收款人（`:97-108`）、退订回执（`:109-119`）、订阅清单三态分组（有效 / 疑似 / 已退订，`:120-146`）。
- `billDetails()`（`:153-157`）、`TransactionRows`（`:159-171`）、`BillDetailsCard`（`:173-188`，>3 笔进 `DetailsDrawer`）、`billSummary()`（`:190-195`）、`BillCardActions`（`:197-226`，月份切换 `type="month"` + 分类下钻）。
- 可复用点：**这是"父任务 → 子任务 → 内联展开"的现成实现**，联动子项完全可以复用 `ActionButton` + `links` + `renderChild` 的形状。

### 2.4 `shell/components/ConfirmationCard.tsx`（58 行）— 确认单

- 输入：`{ view: ConfirmationView; title; emphasize?; active; canConfirm; canCancel; busy; extraActions: SlotAction[]; onAnswer; id }`（`:14-25`）。
- 状态：`live = active && decision==="pending"`（`:26`）；非 live 转只读并打 `ReadOnlyStamp`（`:33`、`:54`）。
- `DECISION_TEXT` 5 态（`:6-12`）。
- 复用点：**`extraActions` 是插槽注入额外按钮的既有口子**（`TaskBlock.tsx:145-147` 用 `slot.confirmationActions`）。

### 2.5 `shell/components/VerificationCard.tsx`（174 行）— 验证码 + 模拟人脸

- 输入（`:53-65`）：`{ view, active, canVerify, busy, adminHref, adminLabel?, onSubmitCode, onResend, onStartFace, onShowDemoCode, id }`。
- 两步骤 `<ol>`（`:118-170`）：验证码（`:119-144`）+ 模拟人脸（`:145-169`）。
- `CodeBoxes`（`:29-51`）：透明 input 覆盖 6 个视觉格（`.sh-code-input` opacity 0.01，`shell.css:153`）。
- demo code 30 秒自动隐藏（`:75-79`）；挑战失效时清空输入与提示（`:81-86`）。
- 关键安全形态：等待人脸时**页面内没有"通过"按钮**，只给管理员入口链接（`:158-167`）。
- 复用点：联动里若"采用方案"需要二次验证，可直接复用本组件，不需要新写。

### 2.6 `shell/components/StatusCards.tsx`（170 行）— 六种通用状态卡

| 组件 | 行 | 输入 | 用途 |
|---|---|---|---|
| `WaitingCard` | `:9-19` | `message, facts, id` | 处理中（`role="status" aria-live="polite"`，`:12`） |
| `InputCard` | `:21-72` | `interaction, active, busy, selectedLabel, onSelect, onSubmitText?, id` | 选项 / 单字段补充（金额、收款人线索等） |
| `ResultCard` | `:74-87` | `view: ResultView, origin, id` | 结果（按 tone 取图标 `:7`；>3 字段进 `DetailsDrawer` `:81-82`） |
| `ReportCard` | `:89-104` | `view: ReportView, origin, id` | 报告（`headline` + 字段 + note） |
| `NeedsAttentionCard` | `:106-129` | `facts, message, canQuery, busy, onQuery, id` | 结果待核实（只查不重发） |
| `RecoveryCard` | `:131-170` | `facts, statusText, reason, resolved, resolvedText?, canDiscard, busy, onResume, onDiscard, id` | 刷新/重登后的"这项还没办完" |

复用点：联动"结果页"可直接用 `ReportCard`（分组统计）与 `ResultCard`（单项结论）；"部分完成"没有专用卡，目前只会落到 `ResultCard` 的 `warning` tone。

### 2.7 `shell/components/TaskRecord.tsx`（31 行）— 记录折叠容器

- 输入：`{ task, messages, latest, children, hasActiveChild? }`（`:7-10`）。
- `needsAction = hasActiveChild || !isTerminal || recovery_required || failed || partially_succeeded`（`:12`）→ **有待办就强制展开且按钮 `disabled`**（`:17-18`）；否则可折叠（`:21`）。
- `aria-expanded` / `aria-controls` / `hidden` 面板（`:17`、`:23`）。
- 复用点：联动父目标作为"一条记录"天然适配；`hasActiveChild` 已经能表达"子项还在办"。

### 2.8 `shell/components/DetailsDrawer.tsx`（22 行）— 明细抽屉

- 原生 `<dialog>` + `createPortal` + `showModal()`（`:8-10`、`:13`、`:20`）。
- 关闭时焦点回到触发按钮（`:14`）；关闭按钮 `autoFocus`（`:17`）；点遮罩关闭（`:15`）。
- 复用点：联动"全部子项明细""资金收尾明细"可直接用。

### 2.9 `shell/components/Primitives.tsx`（76 行）— 基础件

`StatusBadge`（`:5-12`）、`FieldList`（`:14-26`，支持 `emphasize` 放大字段）、`OriginTag`（`:28-32`）、`Notice`（`:34-46`，info→`role="status"`，其余→`role="alert"`）、`Card`（`:48-68`，`section aria-labelledby` + `readOnly`/`highlight`/`badge`/`footer`）、`ReadOnlyStamp`（`:70-72`）、`Spinner`（`:74-76`）。

### 2.10 `shell/components/Chrome.tsx`（184 行）— 页面外壳件

`TopBar`（`:7-39`，连接态 `role="status"` + 演示横幅 `role="note"`）、`MessageBubble`（`:41-51`，`sr-only` 报角色 `:44`；`cardSummary` 折叠原文 `:45-47`）、`TypingBubble`（`:53-59`）、`Composer`（`:61-157`，含语音示例按钮 `:119-136`、键盘处理 `:103-108`）、`ExpiredBanner`（`:159-169`）、`SafetyRail`（`:171-184`）。

### 2.11 `shell/presentation.ts`（97 行）— 展示层纯函数（无 React）

- `CardLink { parentId, childId, selection, revision }`（`:5`）——**前端父子关系的唯一数据形状**。
- `needsAttentionInTree()`（`:6-12`）：递归判断子任务树是否还需要用户动作。
- `selectionKey()`（`:13-17`）：把 `CardSelection` 规范化成字符串键（去重 / 缓存键）。
- `readCardLinks()`（`:19-27`）：从 `localStorage["fe-card-links:"+threadId]` 恢复父子关系，并按 `action` 白名单过滤。
- `taskTitle()`（`:29-48`）：按 `data` 形状 + `module` 生成中文标题（accounts/payees/subscription/bills/transfer）。
- `inputPrompt()`（`:50-60`）：按 `required_fields` 生成问句。
- `TimelineItem` + `buildTimeline()`（`:62-96`）：**消息与任务合并成时间线；被 link 的子任务从顶层移除并嵌进父记录**（`:68-79`、`:86`、`:92-95`）。

### 2.12 `shell/types.ts`（115 行）— shell 的类型层

- `ShellTask<D> = Omit<TaskView,"data"> & { data: D|null }`（`:25`）：**generated 的 `TaskView` 被特化成转账形状（`data: TransferTaskView|null`，见 `api.generated.ts:786-803`），shell 用泛型把 `data` 让给业务插槽**。
- `TaskEnvelope { timelineAt?, task, module }`（`:28-34`）：`module` 来自 `StreamEvent.module`，因为 `TaskView` 自身只有可选 `module`。
- `CardSelection = Omit<CardActionRequest,"request_id"|"source_revision">`（`:26`）。
- `HistoryEntry`（`:44-47`）：input / confirmation / verification 三种历史条目。
- `ShellDataSource`（`:49-84`）：**16 个必选方法 + 5 个可选能力**（`readTransferChoices?`、`submitPayeeDetails?`、`cardAction?`）。
- `AdminDemoSource`（`:86-95`）、`Tone`（`:97`）、`ResultView`（`:99-105`）、`ReportView`（`:107-113`）。

### 2.13 `shell/slots.ts`（40 行）— 业务插槽契约

- `SlotAction { label, onClick }`（`:4-7`）。
- `BusinessSlot`（`:9-23`）：`module`、`label`、`voiceDemoText?`、`exampleHints?`、`confirmTitle?`、`emphasizeField?`、`canModifyConfirmation?`、`summarize?`、`result?`、`report?`、`errorHint?`、`confirmationActions?`。
- `genericSlot`（`:25-28`）兜底；`createSlotRegistry()`（`:30-38`）按 `module` 建 Map，`resolve()` 未命中返回 generic。

> **契约级约束**：插槽是**纯映射器**（"Facts already returned by the server"，`:17`），只能把服务端字段转成 `DisplayField`/`ResultView`/`ReportView`，不持有状态、不发请求、不产 JSX。

### 2.14 `shell/slots/billsSlot.ts`（311 行）— 账单插槽（最完整的示范）

- 形状守卫：`isBillReport`/`isBillDetails`/`isCandidates`/`isAnomaly`/`isSummary`（`:72-97`），先判形状再取数。
- 字段构造：`overviewFields`（`:169-181`）、`categoryFields`（`:140-146`）、`comparisonFields`（`:148-167`）、`transactionField`（`:183-194`）。
- 视图：`summaryView`（`:196-203`）、`detailsView`（`:205-213`）、`anomalyView`（`:215-255`）、`candidatesView`（`:257-265`）、`closedView`（`:267-269`）、`result()`（`:271-280`）、`report()`（`:282-302`）。
- 机器码→中文映射 `REASON_LABEL`（`:42-55`）：**不把契约机器码直接给用户**的既有做法。
- 导出 `billsSlot`（`:304-311`，含 4 条 `exampleHints`）。

### 2.15 `shell/slots/transferDemoSlot.tsx`（65 行）— 转账插槽

- 头注释："Demo-only slot proving the shell can host a business line. Ticket 03 replaces it..."（`:1-2`）。
- `summarize()`（`:12-20`）、`result()`（`:22-53`，覆盖 cancelled / failed / succeeded+receipt / failed+operation）。
- 导出（`:55-65`）：`confirmTitle: "请确认这笔转账"`、`emphasizeField: "amount"`、`canModifyConfirmation: true`。

### 2.16 已有「父任务 / 子任务 / 多任务」雏形（汇总）

| 能力 | 现状 | 证据 |
|---|---|---|
| 父子关系数据 | 有，`CardLink{parentId,childId,selection,revision}`，存 localStorage | `presentation.ts:5`、`:19-27`、`useConversation.ts:260-265` |
| 生成子任务 | 有，`cardAction()` 调 `POST /tasks/{id}/actions` 后登记 link | `useConversation.ts:581-594` |
| 子任务渲染 | 有，`renderChild()` 递归 + 环检测 | `AssistantPage.tsx:54-60` |
| 子任务内联展开 | 有，`ActionButton` + `aria-expanded` | `BusinessCards.tsx:42-72` |
| 子任务折叠/置顶 | 有，`needsAttentionInTree` 递归 | `presentation.ts:6-12`、`TaskBlock.tsx:59-61` |
| 子任务从时间线隐藏 | 有，`buildTimeline` 的 `nested` 集合 | `presentation.ts:70-79`、`:86`、`:93` |
| 多任务导航 | 有，"继续办理"条，点条目会展开祖先 `<details>` 再滚动+聚焦 | `AssistantPage.tsx:117-128` |
| 子任务成功后自动刷新父卡 | 有，退订成功自动 `refresh_query` | `useConversation.ts:596-611` |
| 服务端父子接口 | **前端未接**（后端已有 `GET /api/v1/tasks/{id}/children`，`backend/app/api/app.py:306-310`） | 前端 grep `children` 无接口调用 |

> 结论：现有父子能力全部是**"同一父任务下的卡片动作"**，关系由前端自己记；**没有"目标/子项"这种跨任务的编排概念**，也没有消费服务端 `children`。

### 2.17 可复用组件清单（给新页面的最小集）

| 组件 | 一句话职责 |
|---|---|
| `TaskBlock` | 单任务的全部卡片装配（含恢复门控、历史折叠、结果映射） |
| `TaskRecord` | 一条办理记录的折叠容器，有待办自动展开 |
| `ConfirmationCard` | 确认单，含只读态与插槽注入的额外按钮 |
| `VerificationCard` | 验证码 + 模拟人脸两步骤验证 |
| `StatusCards.*` | 等待 / 补充 / 结果 / 报告 / 待核实 / 恢复六态 |
| `BusinessCards`（+`ActionButton`） | 业务清单卡片，点行生成子任务并内联展开 |
| `DetailsDrawer` | 原生 dialog 明细抽屉（焦点回归） |
| `Primitives` | Card / FieldList / StatusBadge / Notice / Stamp |
| `Chrome` | 顶栏 / 气泡 / 输入栏 / 过期横幅 / 安全须知 |
| `presentation.buildTimeline` | 消息与任务合并、子任务归并 |
| `slots.ts` | 业务插槽契约（纯字段映射） |

---

## 3. 设计系统与适老化

仓库里**并存两套设计变量**：`styles.css` 的 `:root`（简易前端）与 `shell.css` 的 `.sh-root`（v0.4 主前端）。两者都被加载（`main.tsx:4` 引 `styles.css`，`ShellApp.tsx:11` 引 `shell.css`）。

### 3.1 颜色变量

**`styles.css:1-21`（`:root`）**：`--ink:#19332d`、`--muted:#5f7068`、`--line:#dce6e0`、`--paper:#fff`、`--background:#f4f7f5`、`--green:#176d50`、`--green-dark:#10563e`、`--green-soft:#e8f4ee`、`--amber:#83570b`、`--amber-soft:#fff4d9`、`--red:#a3302b`、`--red-soft:#fff0ed`、`--shadow:0 16px 48px rgba(27,62,47,.08)`。

**`shell.css:3-27`（`.sh-root`，主前端）**：`--brand:#ff6a00`、`--brand-press:#e05e00`、`--brand-tint:#fff1e6`、`--success:#067647`、`--danger:#b42318`、`--warning:#b54708`、`--ink:#111827`、`--ink2:#374151`、`--ink3:#6b7280`、`--bg:#f5f6f8`、`--card:#fff`、`--line:#d0d5dd`、`--line-soft:#eaecf0`。

- 语义色映射：`.sh-tone-success/danger/warning/pending/neutral`（`shell.css:88-97`）。
- 设计规范与代码一致：`#B42318` 危险、`#111827` 主文字、**橙底配深字**（`frontend/前端-设计规范-v0.1.md:30-50`）；代码里主按钮确实是 `color: var(--ink)` + `background: var(--brand)`（`shell.css:119`）。
- 金额不用红色（规范 `前端-设计规范-v0.1.md:50`）；金额强调靠字号 `.sh-field-emphasis dd { font-size: 28px }`（`shell.css:104`）。

### 3.2 字号 / 间距 / 圆角 / 阴影

| 项 | shell（主前端） | 简易前端 |
|---|---|---|
| 基准字号 | `.sh-root { font-size: 18px; line-height:1.55 }`（`shell.css:24-25`） | `body { font-size:17px }`（`styles.css:25`），760px 以下 16px（`:341`） |
| 标题 | 20px（`shell.css:39`、`:77`）、22px（`:278`、`:306`） | 19px（`styles.css:74`）、20-27px |
| 正文 | 18px（`.sh-bubble` `shell.css:59`、`.sh-btn` `:118`） | 17px |
| 次要说明 | 16px（`.sh-hint` `shell.css:80`） | 13-14px（`styles.css:75`、`:189`） |
| 金额 | 28px 加粗（`shell.css:104`）、headline 32px（`:105`）、账单合计 32px（`:264`） | 无专项 |
| 卡片内边距 | 20px（`shell.css:73`、`:305`） | 22px（`styles.css:210`） |
| 卡片间距 | 12/16/20px（`shell.css:70`、`:73`、`:237`） | 18-24px |
| 圆角 | 卡片 16px（`:73`）、按钮 12px（`:118`）、选项 14px（`:129`）、徽章 999px（`:86`）、抽屉/品牌块 12px（`:41`） | 9-26px（`styles.css:34`、`:164`、`:210`、`:294`） |
| 阴影 | 仅高亮卡 `0 6px 20px rgba(255,106,0,.12)`（`shell.css:74`）；**无通用阴影变量** | `--shadow` 通用（`styles.css:20`），多卡共用 |

### 3.3 响应式断点

- `shell.css`：`min-width:1100px`（桌面右栏，`:203`）、`min-width:640px`（`:209`）、`max-width:600px`（`:282`）、`max-width:480px`（`:321`）、`max-width:479px`（`:213`）。
- `styles.css`：`max-width:1120px`（隐藏右栏，`:336`）、`max-width:760px`（`:340`）、`max-width:420px`（`:378`）。
- `styles.css:24` `html,body,#root { min-width: 320px }`。

### 3.4 焦点 / 触摸目标 / 减少动效 / 强制色

- 焦点：全局 `outline: 3px solid #8a5a08; outline-offset: 3px`（`styles.css:30-33`）；shell 内覆盖为 `outline: 3px solid var(--ink); outline-offset: 2px`（`shell.css:31`）；抽屉/输入额外 `outline 3px`（`shell.css:114`、`:116`、`:157`）。
- 强制色：`@media (forced-colors: active)` 焦点改 `Highlight`（`styles.css:332-334`）——**shell.css 没有 forced-colors 分支**。
- 触摸目标：`.sh-btn` 56px（`shell.css:118`）、次级 52px（`:121`）、quiet 48px（`:124`）、链接按钮 48px（`:126`）、选项 56/64px（`:129`、`:312`）、输入 56px（`:186`）、发送 56px（`:189`）、话筒 52px（`:182`）、`summary` 44px（`:254`）、`sh-pending-nav` 按钮 44px（`:319`）。简易前端多为 42-54px（`styles.css:119`、`:132`、`:149`、`:199`、`:245`）。
- 减少动效：`styles.css:387-389`（`transition-duration:.01ms; animation-duration:.01ms`）与 `shell.css:216-218`（`animation:none; transition:none`）都有；动画源：`sh-blink`（`:68`）、`sh-spin`（`:136`）、`sh-pulse`（`:160`）、`sh-wave`（`:199`）。

### 3.5 200% 缩放相关现状（如实）

- **全部使用固定 px，没有 rem**：两个样式表中 `rem` 命中 0 次；唯一相对单位是 `shell.css:229` 的 `font-size: 1.1em`（局部）。
- **没有 200% 缩放专项处理**：`frontend/` 下所有 `.md` 中 grep `200%|缩放|zoom` **零命中**；CSS 中也没有针对 `zoom` 或大字号的重排规则。
- 布局对缩放的天然行为：
  - 主壳 `.sh-root { position: fixed; inset: 0 }`（`shell.css:17-19`）→ 应用固定占满视口，内部 `.sh-body { overflow-y: auto }`（`:52`）滚动；缩放到 200% 时不会整页横向滚动，但顶栏 60px（`:37`）+ 输入栏（`:180`）固定高度会挤压内容区。
  - 允许横向滚动的只有一处：`.sh-pending-nav { overflow-x: auto }`（`shell.css:317`）。
  - `min-width: 320px`（`styles.css:24`）在 1280px 屏 200% 缩放（≈640 CSS px）下不触发横向滚动；在 1024px 屏（≈512）也不触发，但会命中 `max-width:600px` 分支。
  - 窄屏分支会把字段行改为换行左对齐（`shell.css:289-290`），是现有唯一"大字号下不挤"的处理。
- 风险（供走查时验证，不是结论）：`position: fixed` 外壳 + 内部滚动在浏览器 200% 缩放下需要实测；`.sh-code` 固定 60px 高（`:152`）与 6 列格子（`:154`）在大字号下可能溢出。

---

## 4. 无障碍现状（先例 + 证据）

1. **读屏汇总区（aria-live）**：`AssistantPage.tsx:74-76` —— `sr-only role="status" aria-live="polite" aria-atomic="true"`，播报"已有 N 条助手回复，X 项等您补充，Y 项需要您确认或验证，Z 项已结束"（数字来源 `:33-38`）。**这是全页唯一的状态汇总播报，新页面应扩展它而不是另建。**
2. **卡片语义**：`Primitives.tsx:48-61` `Card` 用 `<section aria-labelledby={id}>` + `<h3 id>`；调用方传 `labelledBy`（如 `ConfirmationCard.tsx:30`、`StatusCards.tsx:11`）。测试据此用 `getByRole("region"/"heading")` 断言（`shell.test.tsx:75`）。
3. **焦点管理（抽屉）**：`DetailsDrawer.tsx:8-20` —— `showModal()`、关闭时 `trigger.current?.focus()`（`:14`）、关闭按钮 `autoFocus`（`:17`）；测试断言关闭后 `document.activeElement === trigger`（`conversation-layout.test.tsx:87`）。
4. **展开/收起 + 焦点恢复（内联子卡）**：`BusinessCards.tsx:57-70` —— `aria-expanded`、`aria-controls={panelId}`、`useId()`；异步返回后若焦点掉到 `body` 则回填到触发按钮（`:58-61`）；测试验证连点不重复请求且焦点留在按钮（`business-cards.test.tsx:54-62`）。
5. **键盘操作**：`Chrome.tsx:103-108` 话筒按钮支持 Space/Enter 按下/抬起（`onMicKey`），并带 `aria-pressed`（`:123`）。
6. **消息角色播报**：`Chrome.tsx:44` `sr-only` "您说：/助手说："。
7. **跳转链接**：`AssistantPage.tsx:69` `.sh-skip` → `#sh-main`（`main tabIndex={-1}`，`:84`）；`App.tsx:330`、`AdminPage.tsx:144` 同款。
8. **状态/错误播报**：`Notice` info→`role="status"`、其余→`role="alert"`（`Primitives.tsx:37`）；`WaitingCard` `role="status" aria-live="polite"`（`StatusCards.tsx:12`）；验证码演示区 `aria-live="polite"`（`VerificationCard.tsx:128`）。
9. **导航到待办项**：`AssistantPage.tsx:117-128` —— 先向上打开所有祖先 `<details>`（`:121-125`），再 `scrollIntoView` + `focus()`（`:126`）。

> 未发现：跳焦陷阱（focus trap）的显式实现（依赖原生 `<dialog>`）；`aria-describedby` 用法；`role="tablist"`/分步导航语义；`aria-current`；200% 缩放或读屏的实测记录文件。

---

## 5. 数据源层

### 5.1 两条实现 + 选择逻辑

| 实现 | 文件 | origin | 何时使用 |
|---|---|---|---|
| stub | `shell/stub/demoBackend.ts`（914 行） | `"stub"`（`:444`、`:822`） | `API_MODE === "contract-demo"`（`ShellApp.tsx:13-24`） |
| 真实 | `shell/api/realDataSource.ts`（107 行） | `"real-api"`（`:26`） | 其余情况 |
| 契约模拟 | `api.ts` 内置 mock（`mockGet` `:418-489`、`mockPost` `:491-749`） | `"contract-demo"` | `API_MODE === "contract-demo"` 时 `get`/`post` 直接走内存+localStorage（`api.ts:751-752`、`:767-768`） |

`api.ts:16-22`：`API_MODE` 由 `import.meta.env.VITE_API_MODE === "contract-demo"` 决定，`API_ROOT = "/api/v1"`。

> **注意**：`demoBackend` **没有 `cardAction`，也没有 `submitPayeeDetails`**（`demoBackend.ts:443-819` 全量方法里只有 `readTransferChoices`，`:586`）。因此 stub 模式下 `conversation.supportsCardActions === false`（`useConversation.ts:720`），`TaskBlock.tsx:191-206` 的账单/订阅卡动作全部不可用。**stub 只模拟转账形状**（`demoBackend.ts:1-2` 注释、`:21` `MODULE="transfer"`）。

### 5.2 各动作的调用方式（`realDataSource.ts`）

| 动作 | 方法 → HTTP | 证据 |
|---|---|---|
| 进入会话 | `POST /session/enter` | `:28` |
| 读会话 | `GET /session` | `:29` |
| 保证线程 | `GET /threads?limit=100` → 取最后一条，否则 `POST /threads` | `:31-34` |
| 消息列表 | `GET /threads/{id}/messages?limit=100`（自动翻页） | `:36-37`、`pagination.ts:4-13` |
| **任务列表** | `GET /tasks?thread_id={id}&limit=100` → `envelope()` 补 `module` | `:39-42`、`:17-22` |
| **任务详情** | `GET /tasks/{id}` | `:44-46` |
| 任务记录（确认/验证历史） | `GET /tasks/{id}/records` | `:48` |
| 发消息 | `POST /threads/{id}/messages` | `:50-51` |
| 补充输入 | `POST /tasks/{id}/inputs` | `:53-54` |
| 改草稿 | `POST /tasks/{id}/draft` | `:56-57` |
| 转账候选 | `GET /tasks/{id}/transfer-choices?kind=accounts|payees` | `:59-60` |
| 收款资料 | `POST /tasks/{id}/details` | `:62-63` |
| 恢复 | `POST /tasks/{id}/resume` | `:65-66` |
| 取消 | `POST /tasks/{id}/cancel` | `:68-69` |
| 查结果 | `POST /tasks/{id}/query-result` | `:71-72` |
| **卡片动作（生成子任务）** | `POST /tasks/{id}/actions`（body 含 `request_id`+`source_revision`+selection） | `:74-75`、`useConversation.ts:586-587` |
| **读确认单** | `GET /confirmations/{id}` | `:77-78` |
| **确认** | `POST /confirmations/{id}/answer`（`confirmation_version` + `choice`） | `:80-81` |
| **读验证** | `GET /verifications/{id}` | `:83-84` |
| **提交验证码** | `POST /verifications/{id}/code`（`request_id` + `submission_id` + `code`） | `:86-92` |
| 重发验证码 | `POST /verifications/{id}/resend-code` | `:94-95` |
| 演示验证码 | `GET /verifications/{id}/demo-code` | `:97-98` |
| 开始人脸 | `POST /verifications/{id}/face/start` | `:100-101` |
| **SSE** | `subscribe()` → `connectToThread()` | `:103-105` |

**SSE 细节**（`api.ts:806-852`）：`new EventSource("/api/v1/threads/{id}/events", { withCredentials:true })`（`:822`），监听 7 类事件 `message_delta / message_completed / task_updated / interaction_required / report_ready / session_expired / stream_error`（`:823-831`），`onopen`/`onerror` 回调连接状态（`:845-846`），取消时移除监听并 `close()`（`:847-851`）。消费在 `useConversation.ts:267-299`。

### 5.3 `allowed_actions` 如何被消费

- 类型：`AllowedActions = ("provide_input"|"confirm"|"verify"|"query"|"cancel"|"resume")[]`（`api.generated.ts:170`、`:184`）；`contracts.ts:32` 导出 `AllowedAction`。
- grep 统计：`frontend/src` 内共 **81 处**，分布：`demoBackend.ts` 17、`TaskCard.tsx` 17、`api.ts` 14、`TaskBlock.tsx` 8、`useConversation.ts` 8、7 个测试文件合计 13、`api.generated.ts` 2、`AssistantPage.tsx` 1、`contracts.ts` 1（`allowedActions` 驼峰写法 **0 命中**，前端统一用 snake_case 字段名）。
- 三种消费方式，**全部是"服务端说了才算"**：
  1. **决定按钮是否渲染/可用**：`TaskBlock.tsx:73`（能否放弃）、`:88`（能否取消任务）、`:122`（能否补充）、`:142-143`（能否确认/取消）、`:162`（能否验证）、`:183`（能否查询）。
  2. **决定请求是否发出（守卫）**：`useConversation.ts:429`、`:442`、`:453`、`:515`、`:553`、`:561`、`:576`、`:632` —— 每个 action 先查 `includes(...)`，否则直接 return。
  3. **汇总展示**：`AssistantPage.tsx:33-36` 用 `allowed_actions.includes("provide_input")` 统计"等您补充"。
- 旧前端同样口径：`TaskCard.tsx:370-374`（`canConfirm/canCancel/canVerify/canProvideInput`）、`:636-657`。
- 模拟层也用它做门（不是前端自己造）：`api.ts:557`、`:569`、`:622`、`:651`、`:657`、`:663`；`demoBackend.ts:574`、`:634`、`:651`、`:674`、`:680`、`:739`。

> 对新页面的硬约束：联动"采用方案"按钮能不能点，必须由服务端 `allowed_actions` 决定；现有代码里没有"前端推导可执行性"的先例，不要新开这个口子。

### 5.4 刷新 / 重连后如何恢复（`useConversation.ts`）

- 本地存储键（`:8-9`）：`fe-shell-entered`、`fe-shell-history:{threadId}`；另有 `fe-card-links:{threadId}`（`presentation.ts:19-27`）、`fe-task-positions:{threadId}`（`useConversation.ts:146`、`:256`）。
- **启动**（`:227-250`）：`getSession()` → 401 且本地 `ENTERED_KEY==="yes"` 则 `expire()`，否则自动 `enter()` → `loadThread(true)`（`markRecovery=true`）。
- **`loadThread(markRecovery)`**（`:121-217`）：
  - 并发合并：`loadFlight` + `loadAgain`（`:122-126`、`:211-216`），同一时刻只跑一次读取。
  - 同时拉 `listMessages` + `listTasks`（`:133`），再对每个任务 `listTaskRecords`（`:134-142`，单个失败不拖垮整页，401 除外）。
  - `recovery=true` 时**清空并重建**：tasks（`:153-163`）、confirmations（`:164-174`，保留更高 version 的缓存）、verifications（`:175-181`）、cardLinks（从 localStorage 恢复并只保留仍存在的任务，`:183-189`）、history（用 `restoreServerRecordHistory` 以服务端记录顺序重建，`:190-194`、`:30-45`）、`bootRecovery` = 所有"未终结或需恢复"的任务（`:196`）。
- **`bootRecovery` / `recovered`**：`TaskBlock.tsx:39` 用它把任务降级为只读 `RecoveryCard`（`:63-81`）；用户点"查看原任务"→ `actions.resume()`（`:622-629`）→ `settleRecovery(taskId,"resumed")`；点"放弃"→ `discard()`→`cancel()`（`:639-641`）。
- **重连**（`:288-296`）：`isConnected && hadConnection && !wasConnected` → `loadThread(false)`（增量合并，不重建）。
- **消息丢失兜底**（`:303-323`）：`awaitingReply` 期间每 15 秒 `loadThread(false)` 只读补齐，**永不重发**。
- **幂等**：`act()`（`:394-425`）按 `key` 复用 `pendingIds` 里的 `request_id`，只有 4xx（非 429）才丢弃；`submitCode` 特意每次新 id 且失败后改为读（`:513-550`）。
- **测试对应**：`shell/useConversation.recovery.test.tsx` 覆盖漏读回复不重发（`:151-179`）、只清自己的错误（`:181-202`）、单个任务历史失败不影响页面（`:203-218`）、重连合并确认历史（`:220-233`）、重连不叠加读取（`:235-251`）、显示后端中文原因而非机器码（`:253-295`、`:297-320`）。

### 5.5 契约缺口（关键）

- `api.generated.ts` 的 `PublicContract`（`:1571-1609`）**没有任何 Cross / Budget / Birthday / Scenario 类型**；grep `Cross|scenario|Budget|pension|Birthday` 在 `api.generated.ts` **零命中**。
- 只有 `Module` 枚举里出现字符串 `"cross"`（`api.generated.ts:173`、`:187`），以及 `ModuleError.source` 枚举（`:166`）。也就是说：**前端目前只能知道"这是 cross 模块的任务"，但不知道它的 `data` 长什么样**。
- 后端其实已有：`backend/app/contracts/cross.py`（`CrossScenario` = `expense_reduction`/`birthday`/`budget` 等，`:24-30`；`CrossConstraints` `:135`；`CrossStep` `:263`；`CrossTaskView` `:277`；`BudgetView` 等）、`backend/app/modules/cross/*`、`GET /api/v1/tasks/{id}/children`（`backend/app/api/app.py:306-310`）、父子 API 测试（`backend/app/api/test_parent_child_api.py:1`、`:155`）。
- **类型怎么补（已核实，前端目录内可做）**：生成脚本 `frontend/scripts/generate_contract_schema.py` 里有一份**显式白名单 `PUBLIC_MODELS`**（`:46-84`），只登记了 transfer/bills/subscription/security/audit 相关模型，**没有 `app.contracts.cross`**；`TaskView` 还被特化成 `TaskView[TransferTaskView]`（`:57-58`）。因此补 cross 类型 = 在该文件加 import（`:13-44` 区）+ 白名单条目，再跑 `npm run generate:contracts`（`package.json:9`），**不需要改后端**。补完还要在 `contracts.ts` 增导出（现只导出 transfer/bills/subscription 相关，`contracts.ts:2-43`）。

---

## 6. 现有测试

### 6.1 九个测试文件与覆盖

共 69 个 `it` 声明（`shell.test.tsx` 的 `it.each` 展开后 70 个用例）。全部 vitest + jsdom + Testing Library，**没有 E2E**（前端目录内无 Playwright/Cypress）。

| 文件 | 用例数 | 覆盖什么 |
|---|---|---|
| `src/ui-recovery.test.tsx` | 14 | **旧前端**（`/legacy`，`App`+`TaskCard`）：验证码只提交一次、换挑战清空输入、迟到 demo code 丢弃、旧对话迟到响应不串台、明确拒绝后可继续编辑、分页 cursor、任务快照变化刷新验证、跨对话重试沿用 request_id、恢复态按钮禁用、`allowed_actions` 只给 confirm 时不出"修改"、确认单转只读、余额不足引导、高风险终止无继续入口、中文恢复文案（`:9-27` mock `./api`） |
| `shell/shell.test.tsx` | 12（13 用例） | **主链路走查**：确认→验证码→管理员人脸→等待→结果、双击只提交一次、改草稿出新确认单、草稿失败保留表单、409 后刷新并只读、验证码错误终止、刷新后"这项还没办完"并恢复、待核实只查不重发、会话过期锁定并重进、聊天输入验证码被拒、管理员端只答已开始的人脸、未知 module 回退 generic 且 `/v04` 挂载（`:303-309`） |
| `shell/useConversation.recovery.test.tsx` | 8 | 恢复语义（见 §5.4）+ `real-api` 管理员链接主机切换（`:323-337`） |
| `shell/conversation-layout.test.tsx` | 7 | `buildTimeline` 归并、`TaskRecord` 折叠、cardLink 刷新复用不新建子任务、恢复的退订确认落在原行、抽屉焦点回归、交易行信息完整、第 4 行待办关抽屉后仍可见 |
| `shell/business-cards.test.tsx` | 6 | 订阅分组与行绑定、疑似/已退订无按钮、busy 全禁用、账单分类下钻、卡片动作幂等（重试用同一 id）、`realDataSource.cardAction` 的精确 URL/body |
| `shell/cards-remediation.test.tsx` | 6 | `InputCard` 金额表单被拒后保留、普通消息被拒后可改、等待超 15 秒不误判、输入重试沿用 request_id、会话过期结束等待并可重进、SSE 先到的确认单不被慢响应覆盖 |
| `shell/guided-experience.test.tsx` | 8 | `GuidedTransfer` 掩码选择改草稿、发现失败保留事实并可重试、聊天始终发消息不误当补充、刷新失败如实报错、银行拒绝不算成功、多级 refresh 归一个根记录、换月查询绑定新月份、整月区间文案 |
| `shell/slots/billsSlot.test.tsx` | 4 | 报告卡取服务端口语摘要、非 real-api 显示演示横幅、汇总/明细/异常三类映射、失败不编造金额 |
| `shell/api/realDataSource.test.ts` | 4 | `restoreServerRecordHistory` 按创建时间排序、`/records` URL 编码、404 不回落本地、写操作沿用调用方幂等 id |

### 6.2 `shell/stub/demoBackend.ts` 的角色

- 定位（`:1-2`）："Local stub backend for the shell demo. Transfer-shaped demo data only: nothing here calls a bank or the real API, and every fact it returns is labelled as demo data in the UI."
- 实现**两个**源：`user: ShellDataSource`（`:443-819`）与 `admin: AdminDemoSource & StubAdminExtras`（`:821-909`），返回 `{ user, admin, sync }`（`:911`）。
- 状态持久化在 `localStorage["fe-shell-stub-v1"]`（`:18`、`:110-125`），支持 `storage` 事件跨标签同步 + 定时 `sync()` 推进阶段（`:400-402`、`:800-818`）。
- 可调时序：`createDemoBackend({ replyDelayMs, submitMs, bankMs, tickMs })`（`:70-77`、`:97-100`），测试用它把动画时间压到 0/10-30ms（`shell.test.tsx:16`）。
- 故障注入：`setResultUnknownFault()` / `getFaults()` / `resetDemo()`（`:894-908`），被"待核实"用例使用（`shell.test.tsx:244`）。
- 关键限制：**只认"转/汇"关键词建任务**（`:524`），**没有 `cardAction`、没有 `submitPayeeDetails`**（见 §5.1），所以账单/订阅卡动作在 stub 下不可用。

### 6.3 新增页面测试应沿用的模式

1. **优先用 `demoBackend` 而不是 mock `fetch`**：`shell.test.tsx:15-17` 的 `makeBackend()` + `renderPage()` + `sendText()`/`reachVerification()` 辅助函数是标准写法；联动若需要 stub 支持，需要先给 `demoBackend.user` 加 `cardAction`（或新方法）。
2. **纯函数/映射用 `renderHook` 或直接调用**：`useConversation.recovery.test.tsx:74-142` 的 `sourceHarness()` 手写 `ShellDataSource` 是最轻量的数据源替身；`billsSlot.test.tsx:108-115` 直接调 `slot.result?.(task)`。
3. **断言"用户看得见的状态 + 实际发出的请求次数/参数"**，而不是组件内部 state：`shell.test.tsx:105`（`toHaveBeenCalledTimes(1)`）、`business-cards.test.tsx:62`（`toHaveBeenCalledExactlyOnceWith`）、`cards-remediation.test.tsx:66-68`（两次调用 body 相等）。
4. **焦点/键盘断言**：`conversation-layout.test.tsx:87`（`document.activeElement`）、`business-cards.test.tsx:54-61`。
5. **必须打 `<dialog>` 补丁**：`HTMLDialogElement.prototype.showModal/close`（`shell.test.tsx:57-58`、`billsSlot.test.tsx:93`），否则 jsdom 下抽屉用例会失败。
6. **每个测试自清 `localStorage`**：`beforeEach(() => localStorage.clear())`（`shell.test.tsx:59`、`business-cards.test.tsx:35`、`conversation-layout.test.tsx:22`）。

---

## 7. 接入点判断：实现「联动总览 + 子项确认 + 结果页」最自然的位置

### 7.1 grep 结论（如实）

| 关键词 | `frontend/src` 命中 | 说明 |
|---|---|---|
| `cross` | **3**（`api.generated.ts:166`、`:173`、`:187`） | 只有枚举值 `"cross"`，无类型、无组件、无接口调用 |
| `parent` / `child` | 49 处，全部是 `parentId`/`childId`（`presentation.ts:5` 等） | **是前端本地卡片关系，不是服务端父子任务**；无 `/children` 调用 |
| `birthday` / `budget` / `expense` / `pension` | **0** | 前端零占位 |
| `联动` / `生日` / `养老金` / `减支` | **0** | 前端零文案 |

> 也就是说：**前端没有任何联动占位**，一切从零开始；唯一已有的"钩子"是 `module: "cross"` 这个字符串会从服务端流进来（`TaskEnvelope.module`，`types.ts:31-33`），`slots.resolve("cross")` 目前会回退到 `genericSlot`（`slots.ts:34-36`）。

### 7.2 推荐插入位置（按层）

1. **数据层（必须）**：`shell/api/realDataSource.ts` 增 `listChildren(taskId)` 调 `GET /tasks/{id}/children`（后端已存在：`backend/app/api/app.py:306-310`；**`data` 直接是 `TaskView[]`**，见 `backend/app/api/test_parent_child_api.py:166-170`）；在 `shell/types.ts:49-84` 的 `ShellDataSource` 增**可选**方法 `listChildren?`（与 `cardAction?` 同风格，`:69`），保持 stub 兼容。
2. **恢复层（必须）**：`useConversation.loadThread`（`useConversation.ts:121-217`）在 `listTasks` 之后按父任务补拉 `children` 并并入 `tasks`，否则刷新后子任务只在点击时才出现；`bootRecovery`（`:196`）需覆盖"父任务未终结但子任务才是当前交互"的情形。
3. **插槽层（推荐）**：新增 `shell/slots/crossSlot.ts`，形状照 `slots.ts:9-23`，提供 `module:"cross"`、`label`、`exampleHints`、`summarize`、`result`；在 `ShellApp.tsx:20` 注册进 `createSlotRegistry([transferSlot, billsSlot, crossSlot])`。**它只能产字段**，总览的版式放这里放不下。
4. **卡片层（核心）**：新增 `shell/components/CrossPlan.tsx`（总览 + 采用按钮 + 子项列表）与子项行组件；在 `TaskBlock.tsx:190-206` 那一段（与 `BillDetailsCard`/`BusinessCards`/`BillCardActions` 同级）插入，或按 `module === "cross"` 分支渲染。**这是与现有代码最一致的做法**（`TaskBlock.tsx` 已经是硬编码业务卡的装配处）。
5. **子项交互层（复用，不新写）**：子项确认/验证/补充直接复用 `ConfirmationCard`/`VerificationCard`/`InputCard`；绑定方式沿用 `ActionButton` 的 `aria-expanded` + `renderChild` 模式（`BusinessCards.tsx:42-72`）与 `renderChild` 递归（`AssistantPage.tsx:54-60`）。
6. **结果层（复用 + 少量新增）**：单项结果用 `ResultCard`（`StatusCards.tsx:74-87`），分组统计用 `ReportCard`（`:89-104`），"部分完成"目前**没有专用卡**，只能落到 `ResultCard` 的 `warning` tone；资金收尾（冻结/已消费/释放）建议新增一个分组卡，不要塞进 `ReportCard` 的 `fields`。
7. **走查层（流程要求）**：把联动新状态加进 `GalleryPage.tsx:48-92` 的 `Section`，满足 ticket 01 "先提交版式/文案走查"（`.scratch/v05-cross-frontend/issues/01-plan-and-child-interactions.md:49`）。
8. **不要做的事**：不要在 `AssistantPage` 里新起第二套时间线；不要给 `BusinessSlot` 加状态；不要让前端自己算"采用方案=授权全部子项"（与 `spec.md:40`、`:43` 的边界冲突）。

### 7.3 最需要新增的 UI 单元（建议 4 个）

| 新单元 | 职责 | 为什么必须新增 |
|---|---|---|
| `CrossPlanCard`（联动总览） | 目标一句话 + 三条场景入口 + 金额/日期 + "采用这个安排" + 子项进度汇总 | `BusinessSlot` 只能产 `DisplayField`（`slots.ts:18-22`），总览需要自定义版式与按钮；现有卡片没有一个能承载"一个目标下 N 个子项" |
| `CrossStepList` / `CrossStepRow`（子项行） | 每个子项一行：状态徽章 + 一句结论 + "去办理"入口，绑定到真实 `child task_id` | 现有 `sh-business-row`（`BusinessCards.tsx:88`、`shell.css:228`）只是列表行，没有"绑定子任务 + 当前交互"的语义；`ActionButton` 只支持单层 selection |
| `CrossSummaryCard`（结果页） | 已办 / 待办 / 失败 / 结果待核实 / 部分完成 分组 + 资金收尾（冻结、已消费、释放） | `ReportCard` 是"字段平铺 + 单 headline"，无法表达分组与"部分完成"；`ResultCard` 只适合单项结论 |
| `ChildTaskPanel`（子任务容器） | 把 `/children` 返回的子任务渲染成可展开子卡（含状态、返回父项） | 现有 `renderChild` 只认本地 `cardLinks`（`presentation.ts:19-27`），刷新后若无本地记录就丢失；需要一个"服务端来源"的容器 |

可选第 5 个：**状态播报扩展**——现有全局播报只在 `AssistantPage.tsx:74-76` 一处，多子项场景需要"第 2 项等您确认"这类按项播报，建议抽 `useAnnounce` 或复用 `Notice role="status"`，不要新增第二个 `aria-live` 区域。

### 7.4 未发现 / 待核实（不猜）

- **未发现**：任何 cross/budget/birthday/pension 的前端类型、组件、文案、测试、E2E；`api.generated.ts` 未生成 Cross 契约；`realDataSource` 未调用 `/children`；`demoBackend` 不支持卡片动作与 cross 模块。
- **未发现**：200% 缩放或读屏的实测记录、`aria-live` 按项播报、focus trap 实现、`aria-current`。
- **未发现**：`shell.css` 的 `forced-colors` 分支、`.sh-rail` 的实际使用（死 CSS）、`.sh-reply-target` 的实际使用（死 CSS）。
- **已核实的接口形状（可据以写 `listChildren`）**：`GET /api/v1/tasks/{id}/children` 的 `data` **直接就是 `TaskView[]`，不是分页对象**——`service.child_tasks` 返回 `views` 列表（`backend/app/api/service.py` `def child_tasks`），测试按 `listed.json()["data"]` 取数组并读 `item["task_id"]`/`item["status"]`（`backend/app/api/test_parent_child_api.py:166-170`）。子任务同时会出现在 `GET /tasks` 列表里（`:174-175`），并且输入/确认/验证都要打到**子任务**路径（`:180-190`）。
- **待核实（需真实服务）**：`TaskView.module` 是否总会带 `"cross"`（类型上是可选 `module?: Module`，`api.generated.ts:797`）；联动任务 `data` 的最终形状（决定 `crossSlot` 的守卫写法）。

---

## 8. 附：给实现者的三条硬约束（来自代码，不是推测）

1. **卡片只能由服务端事实驱动**：`allowed_actions` 是唯一开关（§5.3）；`data` 必须先做形状守卫再取字段（示范 `billsSlot.ts:61-97`）。
2. **刷新/重连不能发新请求**：一切恢复走 `loadThread`（只读），重试必须沿用同一 `request_id`（`useConversation.ts:394-425`、`:513-550`）。
3. **不要新造一套视觉**：新组件必须用 `Card`/`FieldList`/`StatusBadge`/`Notice`/`sh-btn` 系列与 `.sh-root` 变量（§3），否则会破坏 18px 基准、56/48px 触摸目标与 3px 焦点环的一致性。
