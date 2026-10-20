# 05：替换简易前端与全面回归

Ticket ID: liangshuang-frontend-complete/05
Type: 开发 / 联调验收
Owner: 梁爽（Erwin 集成验收）
Directory: frontend/
Status: done（v0.4。主入口已替换为完整前端并保留 `/legacy` 回滚；真实接口回归、390×844 与桌面适老化走查通过，随 [PR #201](https://github.com/DrErwin/hackerthon-bank-agent/pull/201) squash 合入 main `5b1a021`；评测脚本适配与复跑见 [PR #202](https://github.com/DrErwin/hackerthon-bank-agent/pull/202)/[#203](https://github.com/DrErwin/hackerthon-bank-agent/pull/203)，例外如实记录。**PM 2026-10-20 13:00 决定：照做、不砍范围**；**2026-10-20 01:45 决定：不顺延，本期完成**〔撤回同日 01:41 的 deferred 记录〕）
Package: [frontend-complete/packages/01：v0.4 完整前端实现与替换](../../frontend-complete/packages/01-v04-complete-frontend.md)
Spec: [梁爽完整前端实施规格](../spec.md)
Core scenarios: [FE-01～FE-06](../../frontend-complete/spec.md)
Blocked by: [liangshuang-frontend-complete/03](03-transfer-slot.md)、[liangshuang-frontend-complete/04](04-bills-slot.md) 及所需真实接口可运行
Verification: 切换主入口后运行前端测试与构建；在真实 API 组合重跑转账、账单、刷新恢复、待核实查询、过期 / 重复点击；桌面和 390×844 适老化走查；保存证据交 Erwin 验收。

## 交付与验收

- 正式前端成为主入口，简易前端不再承担默认流程；保留必要回滚依据。
- FE-01～FE-06 均有可定位的验证证据，区分自动测试、契约 demo 和真实联调。
- 已验证的安全门、交易结果与恢复能力不回退；跨目录缺陷回归归属负责人修复。
- AI 审查、CI、Ringo 审查和 Erwin 验收分别记录，不互相替代。

## Comments
- 2026-10-20（PM 01:45 撤回顺延，AI 代填）：本票**留在 v0.4 完成**，同日 01:41 记录的「顺延 v0.5」作废。票 03 转账插槽已合入 main（PR #142 `92ee700`）；替换主入口与全面回归（含替换后复跑 `evals/security/react_evidence.py`、转账 TF-OBS-03—07、FE-01—FE-06 页面证据与适老化走查）在 v0.4 内排期，前置＝票 04 与真实接口可运行。
- 2026-10-21（AI 代执行 · 票 05 收口）：**主入口已替换并完成全面回归**。路由：`/` → 完整前端（ShellApp），`/legacy` → 简易前端（回滚依据），`/admin` 与 `/v04`（含 `/v04/gallery`、`/v04/admin`）保持可用（实测见证据）。前端 `npm test` 38 passed、`npm run build` 通过；构建产物 sha256 `786ccaa8…`。
- 2026-10-21（真实接口回归）：转账确认/验证/成功/刷新只读恢复 + **确认按钮连点两次只提交一次**（8/8 检查）；账单 5 场景 98 项断言全 true；0 预期外 API 失败、0 控制台错误。证据 [2026-10-21-replace-entry-and-regress.md](../evidence/2026-10-21-replace-entry-and-regress.md)。
- 2026-10-21（适老化走查，PM 2026-10-21 00:44 口径：按 v0.1 规范数值 + 修 4 处小的）：390×844 与 1280×800 均 `PASS_WITH_WAIVERS`（硬门槛 0 失败）。已修：链接按钮 18px、选项按钮加粗、390 卡片内边距 20px、卡片间距 16px。WAIVED/后续项如实记录：顶栏标题 20 vs 22、17px 字阶、跳转链接 47.9px（亚像素）、顶栏 60 / 输入栏约 74（大于规范）、引导句 6 条、<480 隐藏用户名、办理须知侧栏仅桌面显示；结构性缺口（px 未随系统字体放大、气泡金额未加粗）登记后续票。对比度按 WCAG AA 补充基线：仅时间戳灰字 4.47:1（门槛 4.5，差 0.03）未达，4 屏出现。
- 2026-10-21（评测复跑，PM 授权跨目录适配）：安全 `react_evidence.py` 适配后 SEC-C-001 9/9、SEC-P-002 15/15 Passed（PR #202，证据 `evals/security/evidence/2026-10-21/`）；转账 OBS-03/04/06/07 Passed、**OBS-05 Blocked**（完整前端单会话入口无对话切换动作，场景不适用；等价保护由 `ui-recovery.test.tsx` 覆盖，旧前端证据见 `evals/transfer/evidence/2026-10-11`，不伪装通过）；全量 153 在干净提交上重跑归档 `evals/transfer/evidence/2026-10-21/`（152 Passed + 1 Blocked，`missing_evidence=true`、红线 `Unverified` 如实记录）。
- 2026-10-21（例外/未覆盖，需 PM 验收时确认）：结果待核实（needs_attention）在真实 local-demo 组合无法构造（模拟银行同进程、无故障注入入口），由组件/契约测试覆盖、记未覆盖；会话过期页未构造人工窗口（401 处置由 OBS-06 覆盖）；真机软键盘/iOS 安全区、生产部署与真实银行未验证；Ringo 本人签核与 PM 验收分别记录，本票证据为 AI 代执行，非真人走查。