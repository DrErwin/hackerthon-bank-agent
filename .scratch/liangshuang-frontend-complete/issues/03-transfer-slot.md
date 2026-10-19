# 03：完整转账业务插槽

Ticket ID: liangshuang-frontend-complete/03
Type: 开发
Owner: 梁爽
Directory: frontend/
Status: resolved（[PR #142](https://github.com/DrErwin/hackerthon-bank-agent/pull/142) squash `92ee700` 合入 main，2026-10-20；真实接口走查 PASS，证据 [evidence/2026-10-20-real-api-walkthrough.md](../evidence/2026-10-20-real-api-walkthrough.md)；审查为 AI 审查、非真人；确认 / 验证交互按 **PM 2026-10-20 豁免**留痕，**非 Ringo 本人审查**；票 04 / 05 顺延 v0.5）
Package: [frontend-complete/packages/01：v0.4 完整前端实现与替换](../../frontend-complete/packages/01-v04-complete-frontend.md)
Spec: [梁爽完整前端实施规格](../spec.md)
Core scenarios: [FE-01、FE-03、FE-04](../../frontend-complete/spec.md)
Blocked by: [liangshuang-frontend-complete/02](02-frontend-shell.md)
Verification: 先以契约 demo 走通候选→确认→验证→等待→结果及恢复 / 异常；真实接口可用后重跑同一路径，结果事实与交易号只认后端返回。

## 交付与验收

- 接真实数据源前，先运行前端公共类型生成，确认导出 `TaskRecordsView` 及最新公共字段，不手写平行类型。
- 接真实 `ShellDataSource` 时，用 F39 `GET /tasks/{task_id}/records` 重建确认 / 验证历史，替换本地缓存编号再经 F14 / F16 查回的变通；验证清缓存 / 跨会话恢复、只读展示及任务所有权拒绝路径。
- 按已确认原型实现转账候选、修改、确认、验证、执行、结果及异常状态。
- 保留历史确认 / 验证记录，防止旧确认、过期操作和重复点击造成再次提交。
- 费用、银行、交易号及最终状态仅展示接口返回；缺字段走公共变更流程。
- 邀请 Ringo 审查确认 / 验证交互，联调结果交 Erwin 验收。

## Comments

- 2026-10-13：承接 [PR #108 返修清单](https://github.com/DrErwin/hackerthon-bank-agent/pull/108#issuecomment-6126114071)。F39 后端已由 PR #109 / #110 / #112 / #111 合入；本票落实类型生成与真实回放接入，不在票 02 的 stub 中提前实现。
- 票 02 的 Ringo 审查为 PM 豁免，不延伸至本票或票 05。接入前核对 Issue #85 的可见性和保留口径复核情况，并请 Ringo 审查真实确认 / 验证和回放边界。
- 2026-10-19：按 PR #142 双轴审查补上三处必修和协助项。单条 F39 失败只缺那张历史卡，不再打断整页；断线重连会合并服务端确认 / 验证历史；真实接口的管理员入口改走 `administratorUrl`，避免覆盖当前登录。另补了记录请求在途去重、重连与失败用例，页面数据源改用共享的 `API_MODE`。真实接口走查和 Ringo 审查仍未做，本票保持 in_review，不标记完成。
- 2026-10-20（收口日，AI 实施者代执行 · 留痕）：PM Erwin 决定**方案 A 只收本票**，票 04 账单插槽、票 05 替换简易前端与全面回归顺延 v0.5；Ringo 审查确认 / 验证交互按 **PM 豁免**留痕（**非 Ringo 本人审查**，票 02 的豁免口径不延伸至本票，豁免不改变长期规则）。
- 2026-10-20 真实接口走查（补齐本票 Verification 项）：GLM `glm-5.3`（Coding Plan 入口）+ 受控后端 + 模拟银行 + Edge 真实浏览器，`/v04` 以 real-api 走「给妈妈转500元，主账户A1」→ 正式确认单 → 点「确认办理」→ 专用验证码 → **转账成功**（银行交易号 `2b2bd26e-894c-478e-b562-f2c885b826ba`）；整页刷新与**新会话跨会话**均以 F39 回放只读确认 / 验证记录，零可用按钮、无恢复门、无卡住占位。9 项断言全 PASS，证据 [evidence/2026-10-20-real-api-walkthrough.md](../evidence/2026-10-20-real-api-walkthrough.md)。同轮 `npm ci → npm test` 4 文件 34 passed、`npm run build` 通过（37 modules / 337.58 kB），合入后 main `92ee700` 复跑一致。已知非阻塞：旧会话历史条目的逐条 F14/F16 刷新返回 409 `SESSION_RECONFIRMATION_REQUIRED`（F39 视图已直接渲染，页面无缺失），v0.5 再处理。
- 2026-10-20 合并：[PR #142](https://github.com/DrErwin/hackerthon-bank-agent/pull/142) squash `92ee700` 合入 main，分支已删除。本票不包含账单插槽与主入口替换；`/` 简易前端保留为联调参照。
