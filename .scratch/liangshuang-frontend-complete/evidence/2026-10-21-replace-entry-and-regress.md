# 票 05 替换主入口与全面回归证据（2026-10-21）

- 票：[liangshuang-frontend-complete/05：替换简易前端与全面回归](https://github.com/DrErwin/hackerthon-bank-agent/blob/main/.scratch/liangshuang-frontend-complete/issues/05-replace-and-regress.md)
- PR：[#201](https://github.com/DrErwin/hackerthon-bank-agent/pull/201)「feat(frontend): 替换主入口为完整前端并全面回归（票 05）」，squash 合入 main `5b1a021`
- 评测适配 PR：[#202](https://github.com/DrErwin/hackerthon-bank-agent/pull/202)（安全 React 证据）、[#203](https://github.com/DrErwin/hackerthon-bank-agent/pull/203)（转账 OBS 浏览器检查），按 PM 2026-10-21 00:44 授权做跨目录最小适配
- 执行：AI 实施者（Lead 会话）代执行 · **AI 代填留痕，非真人 UI 走查、非 Ringo 本人安全审查**
- 环境：真实 local-demo 后端（8000，main 代码）+ 智谱 Coding Plan `glm-5.3` + 模拟银行；前端本票构建产物（`/` 完整前端，`real-api`）；Edge headless；桌面 1280×800 / 移动 390×844
- 采集窗口：2026-10-21 01:0x–01:3x（Asia/Taipei）

## 1. 主入口与回滚路径（实测）

| 路径 | 结果 |
|---|---|
| `/` | 完整前端：`#sh-input` 出现、顶栏「演示用户 · 已连接」、账单句式引导；无简易前端输入框 |
| `/legacy` | 简易前端仍可访问（回滚依据，`银行智能助理` 页） |
| `/v04`、`/v04/gallery`、`/v04/admin` | 旧路径仍可用 |
| `/admin` | 真实管理入口仍可用 |

证据：`route-probe.json`、`route-root.png`、`route-legacy.png`。

## 2. 前端检查

- `npm ci` 通过；`npm test` **5 文件 / 38 tests passed**；`npm run build`（`tsc -b && vite build`）通过，38 modules。
- 构建产物 `frontend/dist/index.html` sha256 = `786ccaa852164c6d7cf038e9b45bebeef4a0771e5d086aeb923caa33694da3d9`（后续评测证据的 `frontend_build_sha256` 与之相同）。
- 路由改造：`App.tsx` 根路径 → `ShellApp`，`/legacy` → 旧 `UserPage`；`ui-recovery.test.tsx` 显式指向 `/legacy`（原默认根路径已被完整前端占据）。

## 3. 真实接口回归（全 PASS）

**转账**（`transfer-entry.json`，8/8 检查 true）：

| 检查 | 结果 |
|---|---|
| 主入口是完整前端 | PASS |
| 真实源、无演示标记 | PASS |
| 真实模型产出可操作确认单 | PASS |
| **确认按钮连点两次只提交一次**（`POST /confirmations/{id}/answer` 1 次、任务数不变） | PASS |
| 专用验证码通过、转账成功且交易号回填 | PASS |
| 刷新后只读恢复、无卡住占位、无恢复门 | PASS |
| 刷新后 0 个可用按钮 | PASS |
| 无预期外 API 失败 | PASS |

**账单**（`bills-walkthrough.json`，5 场景 **98 项断言全 true**、`VERDICT=PASS`）：汇总 / 餐饮明细 / 转账明细（打码账号原样）/ 异常（真实命中夜间规则 + 数据不足中文原因）/ 月报告（无原始明细、无演示字样）；23 次 API 调用 = 18×200 + 5×202，无预期外失败。

## 4. 适老化走查（390×844 与 1280×800）

按 v0.1 规范数值验收（正文 18、金额 28、页面标题 22、按钮 18 加粗、可点 ≥48、卡片内边距 20、间距 16）；对比度规范只写「高对比」无数值，按 WCAG 2.2 AA（4.5/3/3）作**补充基线**如实报告，不作为规范门槛。

按 PM 2026-10-21 00:44 决定实施的 4 处小修：链接按钮 17→18px、选项按钮加粗、390 卡片内边距 16/18→20px、卡片间距 12/14→16px。

两个视口结果均 **`PASS_WITH_WAIVERS`（硬门槛 0 失败）**：

| 检查 | 390×844 | 1280×800 |
|---|---|---|
| 正文最小字号 ≥16（含仅允许 14 的时间戳规则） | PASS | PASS |
| 可点目标 ≥48×48 | PASS | PASS |
| 无横向溢出（document 与逐元素） | PASS | PASS |
| 卡片内边距 20px、时间线/任务块间距 16px | PASS | PASS |
| Composer 在视口内、底部可达 | PASS | PASS |
| 键盘焦点（首个 Tab=跳转链接、聚焦有 ≥2px 焦点环、聚焦元素在视口内） | PASS | PASS |

**记录在案的偏差（WAIVED / 后续项，未改动）**：顶栏标题 20（规范 22）5 屏；17px 字阶 47 处（dt/链接/说明等，规范字阶为 18/16/14 且地板 16 已满足）；跳转链接实测 47.9px（差 0.1px，亚像素）；顶栏 60（规范 56）、输入栏约 74（规范 64）、次级按钮 52、话筒 52——均「大于规范值」，判 WAIVED 并记录；引导句 6 条（UX 建议 1–2 张引导卡）；<480 隐藏顶部用户名；办理须知侧栏仅 ≥1100 显示。**结构性缺口（登记为后续票）**：字号全部 px、未跟随系统字体放大（需 rem 化）；气泡内金额未单独加粗。

**对比度（补充基线）**：唯一未达 AA 的是时间戳灰字 `.sh-time` **4.47:1（门槛 4.5，差 0.03）**，4 屏重复出现；正文/按钮/金额达标；边框类非文本对比度为边界项（规范未给数值，未作为门槛）。

证据：`a11y-390x844.json`、`a11y-1280x800.json`（含逐屏 fonts/targets/contrast/overflow/layout 与焦点序列）与 7 张截图；复跑脚本 `a11y-entry.cjs`。

## 5. 评测复跑（脚本适配后）

- 安全 `evals/security/react_evidence.py`：按完整前端适配后 **SEC-C-001 9/9、SEC-P-002 15/15 Passed**（PR #202；干净提交上的归档证据见 `evals/security/evidence/2026-10-21/` 与 `evals/security/run-log.md`）。
- 转账 `TF-OBS-03—07`（PR #203）：**OBS-03 / 04 / 06 / 07 Passed（React 证据 Passed）**；**OBS-05 记 Blocked**——v0.4 完整前端是单会话入口、没有「切换对话」动作，切换后迟到响应的场景无法经新 UI 投递；等价保护由 `frontend/src/ui-recovery.test.tsx`（迟到历史不进入当前对话）覆盖，旧前端证据见 `evals/transfer/evidence/2026-10-11`。**未用变通断言伪装通过。**
- 全量 153 回归在干净提交 `cd976b9`（`dirty_paths=[]`）串行重跑：**152 Passed / 0 Failed / 1 Blocked**，标准 21/21、缺项追问 8/8、红线违规断言 0，`missing_evidence=true`、红线 `Unverified`、`acceptance=NotAccepted`，归档 [evals/transfer/evidence/2026-10-21/](../../../evals/transfer/evidence/2026-10-21/README.md)；并行 `--jobs 4` 同提交曾出现一次 TF-RCV-08 偶发失败，串行单跑通过，归档以串行为准。

## 6. 明确未覆盖（例外）

- **结果待核实（needs_attention）真实复现**：模拟银行与服务同进程、无故障注入入口，真实 local-demo 组合无法构造「银行结果未知」；由组件/契约测试覆盖，记为未覆盖，未用 stub 冒充真实联调。
- **会话过期页**：真实组合下完整前端自动重新进入；401 处置由 OBS-06 实测覆盖（「点这里重新进入」+ 旧按钮消失），未构造人工过期窗口。
- 真机软键盘弹起、iOS 安全区、生产部署与真实银行未验证（headless 不可证明）。
- Ringo 本人安全/确认交互签核与 PM 验收分别记录，本证据为 AI 代执行，不替代真人审查。

## 7. 证据文件（本目录 = `.scratch/liangshuang-frontend-complete/evidence/2026-10-21-replace-entry-and-regress/`）

| 文件 | 内容 |
|---|---|
| `route-probe.json`、`route-root.png`、`route-legacy.png` | 主入口 / 回滚路径 / 旧路径实测 |
| `transfer-entry.json`、`00-entry.png`、`01-confirmation.png`、`04-result.png`、`05-reload-readonly.png` | 转账回归与连点、刷新只读恢复 |
| `bills-walkthrough.json`、`bills-summary.png`、`bills-detail.png`、`bills-anomaly.png`、`bills-report.png` | 主入口上的账单 5 场景真实回归 |
| `a11y-390x844.json`、`a11y-1280x800.json`、`390-*.png`、`1280-*.png` | 适老化测量与截图（含焦点序列、对比度、溢出） |
| `a11y-entry.cjs`、`transfer-entry.cjs`、`route-probe.cjs` | 可复跑脚本 |
| `security-react-run.log`、`transfer-obs-smoke3.log` | 评测适配的实跑日志 |
