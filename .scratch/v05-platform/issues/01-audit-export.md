# 01：管理端审计导出 F35 与 F24 audit 下载分支

Ticket ID: v05-platform/01
Type: 开发
Owner: Erwin
Status: resolved（2026-10-21 领取并交付；[PR #214](https://github.com/DrErwin/hackerthon-bank-agent/pull/214) squash `b01ceb9` 合入，CI run 39630254969 pass 3m15s）
Directory: `backend/app/api/` + `backend/app/audit/` —— **PM 2026-10-21 授权一次交付**：整轮导出要在审计只读端补一个可选的筛选范围，端点与下载分支在 api；两者同属底座（Erwin），按一次交付、一个 PR 落地，跨两个底座目录在票面如实留痕，不再拆成两票两 PR。
Package: [v04-platform/packages/01：v0.4 底座、Agent 与模拟银行](../../v04-platform/packages/01-foundation-agent-mockbank.md)（#121 原登记为该包范围外的遗留，按 PM 决定提前实施）
Spec: [v05-platform 场景规格](../spec.md)
Core scenarios: 契约 §6.7 F24（audit 分支）、§6.8 F35；继承 [v04-platform P04](../../v04-platform/spec.md) 的「导出范围由后端固定、下载受控、内容脱敏」口径
Verification: E2E 在 `backend/app/api/test_app.py`（HTTP 边界 + 真实运行时 + 真实审计库）：A01 整轮导出与冻结包 / A02 任务范围 / A03 权限与范围拒绝 + 审计下载不绑会话 / A04 冻结与同 request_id 幂等 / A05 脱敏与只读（不调用模型、不触达银行）。证据见 Comments。
Blocked by: None
Source issue: [Issue #121](https://github.com/DrErwin/hackerthon-bank-agent/issues/121)

## 交付

1. F35 `POST /api/v1/admin/audit/exports`：`request_id`、`demo_round_id`、`task_id?` → `ExportView(kind=audit)`；创建即生成并冻结 JSON 证据包（`status=ready`），缺省 `task_id` 为整轮范围。
2. F24 `GET /api/v1/exports/{export_id}/download` audit 分支：复核独立管理身份 + 创建时固定范围，未就绪 409；不绑定创建时会话、不重走验证。
3. 审计留痕：导出与下载各写 `audit.accessed`（`action=export|download`、`export_id`、`permitted`）。
4. 存储：导出资源表允许 audit 导出无报告 / 无会话线程（旧演示库做一次保留数据的结构迁移）。
5. 只读端：`AuditReader.export_json` 支持可选任务范围（不传即整轮），`audit.accessed` 携带 `export_id`。

## 边界与依赖

- 不改公共契约（F24/F35 与 `ExportView` 均已定义），不改安全策略、不触达银行规则；审计数据源只用既有只读端。
- 不在本票：前端管理页入口（PM 决定本次不加，已登记为已知限制）、F25—F32、安全评测覆盖登记（安全线）。
- 审查与验证：AI 双轴审查（规范 / 票面）+ CI，非真人审查；真人安全签核不在本票范围。

## Comments

- 2026-10-21 22:40：PM Erwin 指派「把 121 做了」，确认两条口径——①跨 `api/` + `audit/` 两个底座目录一次交付、一个 PR（票面留痕）；②本次不加前端管理页入口，只交后端契约能力，并注明该限制。建票开工。
- 2026-10-21 23:10 实施完成并开 [PR #214](https://github.com/DrErwin/hackerthon-bank-agent/pull/214)（分支 `v05-platform-01-audit-export`，基线 main `27bc9ca`，合入前 rebase 到最新 main；四个提交：代码+票面 / 证据 / 文档回填 / 证据换行修复）：
  - `backend/app/audit/journal.py`：`_events` / `export_json` 支持可选任务范围（缺省整轮）；`_access` 与 `audit.accessed` 携带 `export_id`。
  - `backend/app/api/store.py`：导出表 `report_id` / `thread_id` 允许空，旧演示库一次保留数据的结构迁移。
  - `backend/app/api/app.py` + `service.py`：F35 端点；F24 audit 分支（复核管理身份、复用创建时范围、不绑会话）；导出/下载 `audit.accessed` 留痕；`audit_reader` 授权支持整轮导出与任务范围导出。
  - `backend/app/api/README.md`：路由表与口径、未做前端入口的已知限制。
  - E2E 6 例（`backend/app/api/test_app.py`：整轮冻结包 / 任务范围 / 拒绝留痕 / 生成故障 / 旧表迁移 / 同 request_id 幂等）：`app/api app/audit` **117 passed**、后端全量 **1191 passed**、模拟银行 **14 passed**（证据 `evidence/2026-10-21/pytest-*.txt`，含全量日志；`capture_pytest_evidence.py` 可复跑采集）。
  - 可复验产物：`evidence/2026-10-21/run_f35_evidence.py`（整轮/任务两个冻结证据包 + `summary.json`：包内 manifest 哈希逐条复算、整轮/任务包与审计库快照逐 event_id 相等、验证码不落包、冻结字节、导出/下载留痕、零模型调用）；`evidence/2026-10-21/check_real_demo_db.py`（旧导出表迁移保留行；真实演示库 3636 事件整轮导出 **5,563,231 B / event 3637 / evidence 864**，三次实测建包 **11.49s / 12.40s / 15.02s**〔最后一次与全量测试并行，偏高〕、下载 **0.026s / 0.024s / 0.030s**；改用 SQLite backup API 只读拷贝并记录源库路径、大小与 sha256：application `d9bea604…` / mock_bank `c5bd11b6…`，不动原件）。每次导出的 sha256 记在当次 `real-demo-check.json`：包内包含本次导出的留痕事件（随机 event_id + 时间戳），因此该哈希随运行变化，**不作为固定指纹**引用。
  - 已知限制（如实登记，不记作已覆盖）：管理前端入口未做（PM 决定）；历史轮次导出与既有 F33/F34 一致只允许当前管理员轮次；`audit.accessed` 事件不带 `task_id`，不经 F33/F34 任务视图读取（既有只读口径，整轮证据包内可见）；F35 在 `mutation_lock` 内同步建包（旧演示库 3636 事件约 12s，测试并行时 15s），长轮次会阻塞其他写请求；未命中本人范围的下载尝试按最小披露返回 404 且不留痕（只有命中已冻结行的 409/403 留痕）；`evals/security/coverage_readiness.py` 仍把 F35 记为缺提供方，归安全线同步。
  - 审查：两个独立子代理双轴审查（**AI 审查、非真人**，无 P0/P1 安全缺陷，结论均为「有条件可合」），意见已按下方「审查处置」全部处理；审查意见与本轮处置见 Comments。

- 2026-10-21 23:47 两个独立子代理双轴审查（**AI 审查、非真人**）结论均为「有条件可合」、无 P0/P1 行为或安全缺陷；意见当日处置并复跑：
  - **E2E 完整性（原唯一 P1）**：原断言用包内自报 `event_count` 自切 journal，属自证；改为导出前快照审计库，整轮断言 `包 event_id 集合 == 快照 ∪ {本次导出事件}`、任务包 `== 该任务快照`，并断言导出/下载只新增 `audit.accessed`、mock bank 操作/流水计数不变。变异（过滤整轮 `tool.*`）已无法再通过。
  - **生成异常**：`export_json` 非权限异常原会留下永久 `preparing`；改为统一 `failed` + `DEPENDENCY_UNAVAILABLE` 后再抛，并补故障用例（503 + 行状态断言）。
  - **拒绝留痕**：命中已冻结导出行的 409（未就绪）/403（非管理身份）现写 `audit.accessed(action=download, permitted=false)` 并区分原因码；补 409 + 同 owner 降级角色 403 用例。未命中本人范围的 404 按最小披露不记录（已登记）。
  - **管理身份复核**：F24 audit 的 role 复核原本不可达且无测试，用「同 owner、role=user 的会话」用例单独覆盖。
  - **迁移 CI 覆盖**：旧 `api_exports`（NOT NULL）重建补 pytest 回归（旧 schema + 旧行 → 连续打开两次 → 行保留且可生成审计导出）；DDL 抽取为单一常量去除重复。
  - **文件名**：改为只用服务端生成的 export id（`audit-<export_id>.json`），不再拼接请求字段进 `Content-Disposition`。
  - **证据**：`run_f35_evidence.py` 修正字段名并新增快照一致性检查；`check_real_demo_db.py` 改用 SQLite backup API、记录源库路径/大小/sha256；`capture_pytest_evidence.py` 增全量后端日志。
  - **测试与证据更新**：`app/api app/audit` **117 passed**、后端全量 **1191 passed**、模拟银行 **14 passed**；证据 `evidence/2026-10-21/` 已重生成（含 `pytest-backend-full.txt`）。
  - 未采纳/留作后续：task-less `audit.accessed` 经 F33/F34 读取需放宽管理只读授权（涉安全口径，登记为已知限制）；F35 异步化不在本票（契约 F35 为同步返回，演示规模可接受）。

- 2026-10-21 23:59 合入：[PR #214](https://github.com/DrErwin/hackerthon-bank-agent/pull/214) 已 squash 合入 main，合并提交 `b01ceb9`，CI run 39630254969 pass（3m15s，whitespace / 文档链接 / Python 语法 / 后端全量 / 模拟银行）。票置 resolved；Issue #121 关闭。
