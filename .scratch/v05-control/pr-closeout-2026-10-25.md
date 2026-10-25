# v0.5 已交付 PR 收口材料（2026-10-25）

Status: materials_ready / awaiting_owner_approval — #303/#304 组合阻塞已归因并定向复验；8 个已交付 PR 的精确 head、目录、差异、原始证据、CI 与风险已核对；提出 4 个合入批次与一次 CI 计费例外申请。**未合入任何 PR、未改任何 PR 分支、未跑真实 E2E。**

## 一、入口修复组合阻塞：已归因并复验（原 scope_blocked 已解除，原证据保留）

1. **v1 现象**：组合检查 201 passed / 13 live skipped、214 唯一节点、0 断言失败，但有 1 次 `socket.bind` 被守卫拒绝且未记录调用栈，`session.exitstatus` 置 1、进程返回 1，整体 scope_blocked。
2. **归因**：用同策略（不放宽任何规则）的诊断守卫重跑一次并复现 ——— 被拒事件是 `urllib3.util.connection._has_ipv6` 在**模块导入期**执行的 IPv6 能力探测：AF_INET6、`bind(('::1', 0))`、无 listen、无 connect、无流量、不在任何测试节点内。`PermissionError` 是 `OSError` 子类，被 urllib3 自己的 `except OSError` 吞掉，所以 214 节点全正常而 exit 为 1。**结论：验证工具分类过窄，不是产品缺陷，也不涉及两 PR 代码。**
3. **处置**：新增 v2 守卫，只对上述帧链（`urllib3/util/connection.py` 的 `_has_ipv6` + 回环 + AF_INET/AF_INET6 + bind + 端口 0）做精确分类并逐条记录；`socket.connect`、非回环、`getaddrinfo`、子进程、临时根外数据库等规则逐字保留。没有放宽到"任意回环 bind"。
4. **定向复验**：同并集、同环境清理、同新绝对临时根 —— **214 唯一节点、201 passed / 13 skipped / 0 阻断、exit 0**；节点集合与逐节点结果与 v1 完全一致；`urllib3_ipv6_probe_events` 恰好 1 条；SQLite 13085 连接 / 145 路径全在新临时根。
5. **证据位置**：worktree `C:/Users/57652/.codex/worktrees/v05-entry-fixes-combination/hackerthon-bank-agent`，分支 `codex/v05-entry-fixes-combination`（本地未推送），提交 `7a68a4b`（归因与 v2 守卫）、`251fad6`（复验产物）。v1 产物（`run-metadata.json`、`combined-tests.xml`、`scope.json`）字节未改，scope_blocked 结论作为历史层保留。

该复验是"当前 main 的运行代码 + 303/304 两个补丁"的局部程序断言，**不是**页面 E2E；主线上自组合基线 `84a3605` 以来只有文档变化，backend 树未动，所以该证据与当前 main 直接对应。

## 二、8 个已交付 PR 的精确事实

| PR | head | 实施目录 | Draft | 落后 main | CI（check run） | 原始产物 | GitHub 审查 |
|---|---|---|---|---|---|---|---|
| [#305](https://github.com/DrErwin/hackerthon-bank-agent/pull/305) | `dbc2d62` | `modules/cross` | 是 | 0 | failure / job 未启动（计费） | **无任何 JUnit/日志** | 0 |
| [#303](https://github.com/DrErwin/hackerthon-bank-agent/pull/303) | `cb16311` | `agent_platform` | 是 | 5（纯文档） | failure / job 未启动 | 2 份 JSONL，sha256 可核 | 0 |
| [#304](https://github.com/DrErwin/hackerthon-bank-agent/pull/304) | `60f0686` | `modules/subscription` | 是 | 2（纯文档） | failure / job 未启动 | JUnit XML 132 例（无 commit 锚） | 0 |
| [#296](https://github.com/DrErwin/hackerthon-bank-agent/pull/296) | `b41ef64` | `agent_platform` | 是 | 26 | failure / job 未启动 | 自身无产物（由 #294 覆盖） | 0 |
| [#294](https://github.com/DrErwin/hackerthon-bank-agent/pull/294) | `6204e14` | `evals/mockbank` | 是 | 26 | failure / job 未启动 | 4 份 XML，57 例/4 xfail 可核 | 0 |
| [#291](https://github.com/DrErwin/hackerthon-bank-agent/pull/291) | `f197601` | `evals/security` | 是 | 34 | failure / job 未启动 | 3 份 gz，解压散列与源码指纹可核 | 0 |
| [#290](https://github.com/DrErwin/hackerthon-bank-agent/pull/290) | `e9f2793` | `evals/mockbank` | 否 | 42 | failure / job 未启动 | XML 153 例（149 通过+4 strict xfail） | 0 |
| [#300](https://github.com/DrErwin/hackerthon-bank-agent/pull/300) | `31e995e` | `evals/cross` | 否 | 8 | failure / job 未启动 | gz 解压 sha256 与 manifest 逐字一致 | 0 |

共同事实：8 个 PR 均未被 squash 进 main；`Repository checks` 全部是**计费导致 job 未启动**（steps=0 + 付款/额度 annotation），没有任何远端测试执行证据，不能读成测试红；GitHub 上全部 0 review、0 评论、0 reviewer；所有"双轴独立审查 PASS"都只存在于 `.scratch` 材料，属 AI 代审，不代真人签核。除 #300 外全部对当前 main 无合并冲突（#300 仅 2 个 `.scratch` 文档冲突，代码目录不冲突）。

**本次新取的原始产物散列**（已固化在 [evidence/2026-10-25-pr-closeout/](evidence/2026-10-25-pr-closeout/)，供批准后复核）：

| 文件 | 内容 | SHA-256 |
|---|---|---|
| `pr296-294-combo-on-main.xml` | 批次 5 组合：57 节点/53 passed/4 strict xfail | `15e2d5a96f552442a904fe9be520fb224c681ab47a2613195d0eb1e910a2764d` |
| `pr294-only-reverse-control.xml` | 批次 5 反向对照：49 节点/44 passed/1 failed(旧订单只到待确认)/4 xfail | `03e6baf42640169629c47ff34d0d127c5751092f91dabbd52139b09087ca463a` |
| `pr305-cross-filtered.xml` | #305 作者原命令：90 passed/3 deselected | `f69e9a5f7fa703cbcc4e928ea822214c796f3b94c174c1c3b63c878e611b7b0a` |
| `pr305-cross-full.xml` | #305 整目录：93 passed/0 failed | `362d88b5cb0cb5e1189908b54c09fe63576a89aa386a7d89025adee992e27b20` |

**准确 head 的 CI 事实（均为计费未启动，无执行证据）**：

| PR | check run / job |
|---|---|
| #305 | run `40202032458`（head `dbc2d62`） |
| #303 | run `40190238859` / check `121159485732` |
| #304 | run `40193633934` / check `121169705294` |
| #296 | run `40174157720` / job `121111135876`（正文引用的是旧 head `ac31e2e` 的 run `40171713488`） |
| #294 | run `40177627355` / job `121121649844` |
| #291 | run `40171500613` / job `121103092488` |
| #290 | run `40167884424` / job `121092542796`（正文引用的是上一 head `1fb213b` 的 run `40167839557`） |
| #300 | run `40187827679` / job `121152269529` |

## 三、拟合入批次（按依赖与风险排序）

### 批次 4：#304 → #303（入口修复，同批连续合入）

- **证据**：见第一节 —— 两补丁在**当前 main 运行代码**上的组合复验 201 passed/13 skipped/0 阻断；v1 原始 214 节点、132 节点覆盖与失败留痕未改写。#303 另有可核 sha256 的真实路由 JSONL（13/13，0 业务任务/0 银行操作）。
- **顺序说明**：#304（订阅入口显式停扣判定）先合，随后 #303（平台按完整生活目标选入口并撤掉提示词里的"退订优先"旧规则）。反序会在中间态让旧入口失去旧提示词规则而新规则未生效，故按此序；两支同批合入，中间态不单独宣布可用。
- **同步**：两支各落后 2/5 个**纯文档**提交，代码零差异；同步后需保持原补丁等价（range-diff 核对），再 mark ready、逐个 squash。
- **批准需接受**：S01 真实页面仍 Failed（本批不修、不重跑）；13 个真实路由小样不等于页面/HTTP 验收；两个词法规则都不宣称完整中文理解。

### 批次 5：#296 → #290 → #294（平台订单来源门 + 银行轮次证据）

- **依赖**：#294 的 base 是 #296 分支，且分支历史上物理包含 #296 的 4 个提交；#296 合入后 #294 必须 rebase 到新 main 只保留自身补丁，再 retarget base=main。#294 原组合证据里的 41 个 bank 节点来自 #290 的 `test_birthday_bank_eval.py`（该文件未跟踪于 294 分支），所以按"#290 先进 main，再合 #294"的顺序，使合入后的 main 能复现同一节点集。
- **证据（中控独立复核）**：在**当前 main `8925d54` + #296 自身 4 提交 + #294 自身 7 提交**的组合提交 `e78ad43`（backend tree `d10d8f10`、evals tree `da980d18`，零冲突；13 个改动路径逐字节等于各自 PR head）上，跑 #294 原并集四个文件（`test_birthday_bank_eval.py` 不在三个分支上，按 #290 head `e9f2793` 的 blob `603e31f6…` 逐字节放入后运行、跑完删除）：**57 节点 / 53 passed / 0 failed / 0 error / 4 xfailed(strict) / 80.74s**；4 条 xfail 的 message 均为 "Open round-boundary gap…"。按文件拆分与两支原报告一致（3+8+5+41）。XML：[pr296-294-combo-on-main.xml](evidence/2026-10-25-pr-closeout/pr296-294-combo-on-main.xml)。
- **反向对照（证明 #296 的来源门真的生效）**：main + 仅 #294（无 #296）上跑同目录存在的 3 个文件（#296 新增的 8 节点测试不存在）：**49 节点 / 44 passed / 1 failed / 4 xfailed**，失败节点 `test_current_task_rejects_old_order_and_pays_its_own_order` —— 断言 `denied.decision is SecurityDecisionCode.BLOCK` 得到 `REQUIRE_CONFIRMATION`：无 #296 时旧订单还能走到"待确认"，有 #296 时是 BLOCK。XML：[pr294-only-reverse-control.xml](evidence/2026-10-25-pr-closeout/pr294-only-reverse-control.xml)。
- **复现口径**：pytest 路径相对**仓库根**（`../evals/...`，不是 backend 目录），这是 PR #294 自己文档里的写法；`--runxfail` 未使用。
- **风险**：#296 改的是平台安全门 `scope_authorizer`（对 `bank.capture_frozen` 追加订单来源校验），属两向门变更；#290 的 4 项 strict xfail 属"裸银行对象接口"层缺口，与 #296 的平台授权层不同层，**不得因合入而关闭**，`round-boundary-gap.md` 仍标记"转给 Erwin"。
- **批准需接受**：#296 自身没有落盘测试产物（合入依据为本批组合运行与 #294 的可核 XML）；#290 正文的 CI 链接指向上一 head（当前 head 的 run 亦为计费未启动），合入记录需写清；真实页面 E2E 未跑。

### 批次 6：#291 / #300（评测与证据，可独立，无产品行为变化）

- **#291**：`evals/security` 口径修正，155 passed 报告解压后的 `source_sha256` 与 head 上 `security_runner.py` / `test_security_eval.py` 实测一致；原 152 passed/1 failed 失败批保留；**整体联动安全专项仍 BLOCKED**（内容未完成，不是测试失败）；D 批证据 `base_commit` 不在 head/merge-base/任何分支，属 rebase 前同名提交，作为限制记录，不据此宣称对齐。
- **#300**：S01 首批真实失败的冻结证据，解压后 JSON sha256 与正文/manifest 逐字一致、4 个附件散列一致；**S01 仍 Failed，本 PR 只记录不修复**；与 main 在 2 个 `.scratch` 文档冲突，合入时以 main 版本为基、并入本票新增证据段，不覆盖 main 已有内容；`evals/cross` 代码与证据不冲突。
- **批准需接受**：两支都"保留失败/BLOCKED"，合入不等于缺口关闭；#291 属评测代码（非纯文档）；#300 需一次文档冲突解决。

### 批次 7：#305（cross06 生日个人预算采用与冻结前占用）

- **依赖**：正文声明依赖 #293/#298/#299/#288/#289，全部已合入；分支落后 main 0 提交，无需同步。
- **证据（中控独立复核）**：在 #305 head `dbc2d62`（backend tree `66e106ee`）的隔离 worktree 上：作者原命令 `pytest app/modules/cross -q -k "not receipts_match_real_bank and not controlled_delivery_http"` 得 **90 passed / 0 failed（3 deselected）**，与自述一致；不带 `-k` 的**整目录 93 passed / 0 failed**（147.2s），即被排除的 3 条也通过。XML 已固化：[pr305-cross-filtered.xml](evidence/2026-10-25-pr-closeout/pr305-cross-filtered.xml)、[pr305-cross-full.xml](evidence/2026-10-25-pr-closeout/pr305-cross-full.xml)。
- **风险（本批最大）**：唯一修改产品行为的 PR —— 无已采用个人预算时不再伪造月度 budget_id、也不再在该路径直接冻结；**删除并重写** 2 条既有回归（`test_b07_shared_monthly_budget_cap_blocks_over_cap_freeze`、`test_b05_requery_after_budget_filled_fails_and_reverses`）并把 2 处断言从"占用/active"改为空（`test_cross_birthday.py` L316、`test_birthday_delivery_view.py` L90 均为 `assert commitments == []`）；`@serialized` 仅进程内串行，不承诺多进程原子性。
- **被删回归的覆盖情况（静态对照结论）**：
  - "月预算上限不足阻止冻结"：由**新语义**用例 `test_personal_budget.py::test_bg10_insufficient_room_stops_before_freeze` 覆盖（停在冻结前、`freeze_executes==0`、提示"个人预算"+"暂停"）；但旧的**后置失败语义**（`budget_exceeded`/原额退回）在 head 全仓已无任何匹配，也没有用例再构造"同月已被他任务占满"的既有占用。
  - "预算填满后重新查询失败并回退"：**没有等价用例**；最接近的 `test_bg17`/`test_bg18`/`test_b05_original_freeze_query_without_personal_adoption_keeps_its_reference` 结果不同。
- **顺序**：排在 #296 之后（平台生日门先于 cross 生日编排）。
- **批准需接受**：真实采用/业务预算约束/E2E 均未运行（`budget-e2e-acceptance-design.md` 的 BE01—BE08 全部"未运行"）；本批不因合入启动生日 E2E。

## 四、本次申请（一次答复即可）

1. **批准批次 4—7 共 8 个 PR 按上述顺序合入**，并**仅对本批**采用已记录的本地验证/原始产物作为计费故障期间的合入依据；CI 继续记 **Blocked**，不伪造绿灯、不代签真人审查。允许"不改变受测实现的主线同步"（rebase、仅文档/证据等价、#294 retarget、#300 文档冲突合并）；若出现新业务代码、未解决冲突或验证失败，暂停该项、修复复审并更新材料，不把批准扩成任意改动许可。
2. **批次 5/6 的"保留失败"按现状合入**：#290 四 xfail 保留并转 Erwin 裁定、#291 整体专项仍 BLOCKED、#300 S01 Failed 保留；合入不等于关闭这些缺口，也不等于页面验收。
3. **批次 7 的产品行为变更与既有回归改写**在本人已知情下合入（见上方风险），真实生日/预算 E2E 仍由本人后续运行。
4. **#300 的两个 `.scratch` 文档冲突**授权按"main 版本为基、并入本 PR 证据段"解决（只动本票材料文档，不动 `evals/` 代码与证据字节）。

**不包含**：共享库迁移与应用库 v5→v6 回退；#160 未知放行政策；#216/#227；前端页面批准、200% 缩放与读屏；最终安全/体验接受；S01/S02—S05 或任何真实模型/页面/银行 E2E 启动；Ringo 真人签核。

## 五、执行与登记方式（批准后）

1. 逐个 PR：以准确旧 head 做 `force-with-lease` 同步（仅等价 rebase/文档），核对 range-diff、目录边界与新 head 的 CI annotation（仍为计费未启动）。
2. 按批次顺序 `expected_head_sha` squash 合入；#294 在 #296 合入后重建/retarget；#300 先解文档冲突再 squash。
3. 每项登记：最终 head、squash 提交、准确 head 的 CI 事实、沿用/新增的验证证据与限制；合入后核对主线 backend/evals 树与受测树一致（等价同步不重复跑全量）。
4. 合入后删除远端功能分支、清理本地 worktree；共享跟踪只在文档 worktree 同步，纯文档按仓库例外不跑 CI。
5. 不启动任何真实 E2E；`Issue301`（S01 路由）、`Issue302`（订阅明确停止）仅在合入后按各自范围更新，不据此宣称 S01 通过。

## 六、本次没有做的事

- 未合入任何 PR、未改任何 PR 分支或 Draft 状态、未触发/重跑 CI、未改 PR 描述。
- 未跑真实模型、真实页面、真实银行或任何 E2E；未迁移共享库、未打开共享演示库。
- 未代签安全审查，未把 AI 审查或本地验证写成真人接受。
- 生日"等待期修改"的完整支持已按本人问题卡答复登记（见 [birthday-owner-decision.md](birthday-owner-decision.md)），不再重复询问同一选择；该裁定不含实现开工、PR 合入或页面批准。
