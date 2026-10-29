# 12：生日一次响应丢失的隔离运行装配

Ticket ID: v05-cross-platform/12

Package: [v05-cross-linkage/packages/01-platform-bank：公共接缝与模拟银行](../../v05-cross-linkage/packages/01-platform-bank.md)

Spec: [公共接缝与模拟银行规格](../spec.md)；本票补充下述已授权的装配范围。

Type: 开发

Owner: Erwin（v0.5 统一承担）

Directory: `backend/app/agent_platform/`

Status: merged — [PR #289](https://github.com/DrErwin/hackerthon-bank-agent/pull/289) 已合入 `31e9f274`；原本地验证与双轴审查保留，CI 计费未启动，真人接受另记。2026-10-29 核对。

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
- 后端全量：本 worktree 独立虚拟环境，从 `backend/` 运行 `python -m pytest -q --basetemp=<本worktree专属临时目录>`，**1591 passed in 1035.03s**；另跑 `../evals/mockbank/test_mockbank_eval.py`，**14 passed in 2.75s**。源码未改风险政策，测试只用各自临时数据；没有真实模型调用。
- 提交/交付：[PR #289](https://github.com/DrErwin/hackerthon-bank-agent/pull/289)，分支 `codex/v05-platform12-birthday-response-loss`；代码提交 `1ffb647`，后续提交只记交付证据。已从 `origin/main` 的 `9a479ea` rebase（其相对核查基线仅前端/文档变化，后端代码一致）；未自行合并。
- CI：head `5a127be` 的 [Repository checks](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/40167677934/job/121091952202) 为 failure，注解明确“job was not started because recent account payments have failed or your spending limit needs to be increased”。未跑测试，不能写绿 CI；本票不代批计费例外。后续纯文档提交按路径过滤不主动触发/等待新 CI。
- 内容、相对链接/锚点、围栏、编号、差异空白及改动代码语法检查通过。原链接脚本会扫描本地 `.venv` 中上游依赖的失效 README 链接；本轮只在内存排除 `.venv` 后核对项目文档通过，检查器未改；自己的 `.scratch` 材料另行核对。
- 未完成/未替代：真实模型、生日 HTTP/页面 E2E、真人安全签核、PM 接受均未由本票完成。可解锁隔离故障复现和银行原操作观察；不能据此解锁 XL-B06 联合验收或个人预算验收。
- 独立 Spec 审查：本票实现 PASS、范围内必须修复 0；另实测发现跨目录 P1——[冻结未知后取消，回查重新进入下单](../research/birthday-unknown-cancel-gap-2026-10-25.md)，交中控安排 cross 业务票。XL-B06 未知后停止的联合验收仍 blocked，本票未将其写成通过。
- 独立 Standards 审查：PASS；提交说明缺原因正文 1 项已补齐并复核，范围内必须修复 0。独立 Spec 审查追加材料复核 PASS。没有用 AI 审查代替真人安全批准。

## 2026-10-25 待合入准备（中控续派）

- 原独立worktree同步 `origin/main` 的 `36f1d663b73a1511d2ddc362eb39bd4f972f0e76`，无冲突rebase；三条原提交逐一range-diff为相同补丁。运行代码补丁标识前后均为 `4ccf578318fdbf5289a2083e3582f1fde2d023b4`，差异仍只含平台目录及本组材料，沿用原独立两轴审查（必须项0）。原代码提交rebase后为 `a3c95b9`。
- 新主线相对原基线没有backend/app运行实现变化；针对当前重定基组合复跑本票两文件 **21 passed in 33.15s**。链接/锚点/围栏、差异空白通过；没有新增并发全量，原1591项与银行14项保留原运行基线，不改写成此次新全量。
- 中控本轮转达Erwin已批准首批270/285/287/288/289合入及CI计费本地验证例外；本票289在批准范围内，**296不在范围内**。这不是CI通过、真人专业签核或页面体验接受；本执行对话仅推送准备结果，不自行合并。
- 为前序squash后的独立移植，保留 `refs/codex/v05-platform14-stack-base = 18a3f39bf137f26909b2bd1451a76f6958cd1920`。296仍为原head `296f2eb`，14的三条提交 `4a414ac / ac31e2e / 296f2eb` 未动；等中控合289后通知，再仅移植这三条，不重复带入平台12。
