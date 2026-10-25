# 12：生日一次响应丢失的隔离运行装配

Ticket ID: v05-cross-platform/12

Package: [v05-cross-linkage/packages/01-platform-bank：公共接缝与模拟银行](../../v05-cross-linkage/packages/01-platform-bank.md)

Spec: [公共接缝与模拟银行规格](../spec.md)；本票补充下述已授权的装配范围。

Type: 开发

Owner: Erwin（v0.5 统一承担）

Directory: `backend/app/agent_platform/`

Status: in_progress

Blocked by: None（[v05-cross-platform/09：生日工具、权限与演示装配](09-birthday-runtime-wiring.md)，PR #279 已合入）

Execution assignee: Codex，运行装配遗留线

Accepted by: Erwin 授权 Codex 执行

Accepted at: 2026-10-25

Core scenarios: XL-B05—B06、XL-X07—X08，见[共享规格](../../v05-cross-linkage/spec.md)。

Verification: 在独立临时数据库上，从真实生日入口完成确认/双因子后观察超时；B14 按原编号回查，冻结仅一次，后续写入不再次超时；默认关闭、无授权零写入、原生日停止和正常路径回归。模型替身仅用于构建，不调用真实模型；HTTP/页面 E2E 归原 E2E 包。

## 授权与最小规格

来源：2026-10-25 中控分派，明确允许核对票 09 的 B28 残留后，在本目录追加下一个空闲票，最小实现默认关闭、服务端控制、隔离演示/测试的故障装配。创建前核对本组编号 01—11，12 未使用。

现有银行 `MockBirthdayBank.arm_response_loss(user_id)` 会在下一次生日写入落库后延迟 6 秒；真实网关 4 秒超时返回未知，B14 可查询原操作。现有 `build_runtime` 未调用此入口。

增加服务端 `birthday_response_loss_once: bool = false` 本地配置；打开时仅在本运行实例初始化时，为配置里固定的演示用户武装一次。复用原银行与真实安全门；不新增前端/模型/普通业务可调用的管理入口，不修改 B28 管理协议、不宣称完成 B28 HTTP 管理能力。配置只用于专属数据目录的单进程隔离实例；每次新建运行实例都会重新武装，演示后应关闭再重启。

2026-10-25 实际故障回归发现同目录接线缺陷：旧 `bind_freeze/requery` 只查银行，没有经已有执行器核实原 claim；冻结已查到成功，claim 仍 unknown，限定释放正确暂停，完整生日停在 RUNNING。最小修复仅重接已有执行器的“已有 claim 只读查询”分支，核实后更新原执行记录；缺 claim 拒绝查询，不新建操作，不放宽安全门或释放条件。银行明确失败同样作为已完成观察记录，业务结果仍为失败。

## Acceptance criteria

- [x] 旧配置缺省关闭，示例显式关闭；只有服务端配置能武装一次故障。
- [x] 未批准/未验证的写入仍拒绝；故障不产生授权。
- [x] 真实写入成功但调用超时，任务保持待核实，B14 按原 `operation_id` 找到成功；恢复不再提交冻结，后续操作无第二次故障。
- [x] 不改 API/services/storage/contracts/security/modules/cross，不新增银行规则；原生日正常和停止收尾回归通过。
- [x] 独立子代理按仓库规范与原票/规格审查，范围内必须项已清零；代码独立 PR 回中控，不自行合并或代签验收。

## 核对但不实施的跨目录缺口

`CrossStartInput.constraints.budget_ref`（包括 version）已有公共模型；`CrossEntry.start` 只取 goal/scenario，未传入 constraints；生日流程另建 budget_id 并固定 version=1。另缺采用预算的持久读取/改版能力。提供方与最小复现见[预算缺口核查](../research/birthday-budget-gap-2026-10-25.md)，建议中控拆 storage → cross 依赖，接在 business05 后顺序实施，不在平台绕过预算约束。

## Delivery record

- 基线：`e9517b8466f4ca408a6173c2be7d87b116efe5a8`，隔离 worktree `v05-runtime-risk`。
- 定向回归（本 worktree 独立 `.venv`）：`app/agent_platform/test_birthday_runtime_wiring.py app/agent_platform/test_local_demo.py`，**21 passed in 77.18s**。真实生日入口/门/银行，模型构建替身；本地装配套件另含进程内 HTTP 对照，不属于生日页面或真实模型 E2E。
- 故障前后：新增回归初次 **1 failed, 4 passed**，真实暴露 unknown claim 未核实导致余款释放暂停；只接已有执行器观察后 **5 passed**，再增加“银行查询失败保持未知”“缺 claim 不写”“旧配置默认关闭”断言后上述 21 项通过。
- 最终账实：冻结仅一笔 50000 分；核销 19900 + 26800，释放 3300；原冻结操作编号未变，未知银行查询失败未伪造完成。无授权及未完成双因子时零冻结。
- 后端全量/独立子代理审查/PR：进行中；真实模型、生日 HTTP/页面 E2E、真人安全签核、PM 接受均未由本票完成。
- 独立 Spec 审查：本票实现 PASS、范围内必须修复 0；另实测发现跨目录 P1——[冻结未知后取消，回查重新进入下单](../research/birthday-unknown-cancel-gap-2026-10-25.md)，交中控安排 cross 业务票。XL-B06 未知后停止的联合验收仍 blocked，本票未将其写成通过。
- 独立 Standards 审查：PASS；提交说明缺原因正文 1 项已补齐并复核，范围内必须修复 0。独立 Spec 审查追加材料复核 PASS。没有用 AI 审查代替真人安全批准。
