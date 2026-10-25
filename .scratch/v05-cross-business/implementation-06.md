# business/06 实施与交付证据

Status: developed / local_verified / E2E_pending / CI_blocked — 2026-10-25；本轮开发必要验证，E2E设计完成后停，实际验收由Erwin后续运行。
Worktree: `v05-cross-budget-06`；branch `codex/v05-cross-business-06`；创建基线main `1b3afec5336e5906f87259c7b1c903823cc574e1`；已同步最新main `8925d547eeb19d2e203faed72549e60c5e8a313a`。
代码审查与最终Cross测试head：`caaa5d605e27eeabf445050d418c9fd48ccc77eb`；后续仅本票交付记录。
PR：[Draft #305](https://github.com/DrErwin/hackerthon-bank-agent/pull/305)，已挂当前执行对话，未合并。
Owner: Erwin授权执行对话；只改Cross及本票材料，不修改shared tracker/completion。

## 真实前置与范围

293预算记录/连续版本已合`9d6d899`；298平台来源已合`6ce7fb0`；299真实API分流已合`1b3afec`；288/289已合。
实际读取ApplicationStore接口、`agent_platform/budget-inputs-seam.md`及API专用分支，不拿设计期草稿当接口。
使用本机implement说明手工执行（disable-model-invocation且无斜杠接口）；用户禁止盲跑全后端，覆盖其通用全量建议。
第三批CI例外仅293/299，不延伸本票；不合并本票。08、G1/G2/G3与平台01—05仅规划不实施。

## 行为与兼容

- 保留完整constraints进入请求身份和生日状态；上限、付款账户、原时间精度、受控引用不被默认值覆盖。
- 专用F10当前来源、当前交互/选项、完整原候选/计划及发布摘要共同核验；模型知道选项仍不能采用。
  候选展示时冻结原预算版本；采用用稳定record/expected revision重放，来源记录的phase/completion变化不妨碍只读历史核实。
- 无真实采用则不造用户月度budget_id/预算视图/占用；旧测试以虚构月度ID作预算的断言已改为明确非采用，
  真实采用后的额度不足/未知/收尾保护由新增Cross06用例负责，未改E2E固定数据或风险夹具。
- 个人used/remaining引用原L01完整范围；读窗与逐笔交易核实、公开原任务捕获投影、所有版本未结占用和closed消费分别处理。
  新资金动作重核，冻结前先持久pending及原号；单进程user/round临界区不跨用户交互等待、不宣称多进程保证。
- 原API对带非空Cross数据的配送响应泛型缺口已在05记录。本票配送仍发生在资金前，沿05既有data=None入口，
  个人预算事实留在检查点，后续方案/资金等待和回执继续展示；未跨目录修API，也不提供付款后改配送。

## 验证与停止线

所有本票测试库使用新绝对basetemp `C:/Users/57652/AppData/Local/Temp/v05-budget06-*` 的独立子目录。
新用例使用真实Harness/F10来源、checkpointer与ApplicationStore；多数L01/资金为清楚标注的契约受控替身。
另有真实已注册L01+模拟银行只读+F10采用接线用例，核对实际used与零bank operation；不跑真实资金完整链。
开发中失败已修回。固定实现版本的局部结果如下；不将这些成绩写成E2E通过。

本轮不运行原`test_receipts_match_real_bank*`/`test_controlled_delivery_http*`完整路径，实际页面/模型/银行E2E不运行；
按[独立E2E验收设计](budget-e2e-acceptance-design.md)交Erwin后续验收，既有E2E证据不冒充本票实测。
不打开或迁移共享库，不动原前端工作区或既有E2E数据。未运行后端全量/真实模型/503诊断。

### 局部命令及结果

环境：`D:/hackerthon-bank-agent/backend/.venv/Scripts/python.exe`，PYTHONPATH为本worktree的绝对backend。

| 范围 / 命令尾部 | 结果 | 独立basetemp |
|---|---|---|
| `-m pytest backend/app/modules/cross -q -k 'not receipts_match_real_bank and not controlled_delivery_http' --tb=short` | 90 passed, 3 deselected；含32个个人预算用例 | `C:/Users/57652/AppData/Local/Temp/v05-budget06-final-regression-02` |
| `-m pytest backend/app/agent_platform/test_budget_inputs.py backend/app/api/test_budget_inputs_api.py -q --tb=short` | 58 passed；既有平台来源与API输入接口回归，不是生日资金E2E | `C:/Users/57652/AppData/Local/Temp/v05-budget06-interface-01` |

新增32个用例覆盖完整constraints冲突、零本次上限、真实F10/模型拒绝、modify/decline/旧交互、写后崩溃与取消后只读补原结果、
冻结前pending、未知取消、未核实释放保留、L01不稳定、无引用绑定、旧版本占用、并发首次采用/抢额度、消费入账交错、
closed账单延迟/范围外历史、缺跨任务结算投影、冻结后新采用及真实L01只读接线。BG框架剩余跨主体/会话、页面及完整资金故障组合按E2E设计后续执行，不声称24组所有运行层均通过。

配送规则按2026-10-25用户答复沿用既有旧交互/失效会话/主体轮次任务隔离与重复请求重放，不新增独立有效期。

## 两轴独立审查

初轮固定基点`8925d54`、实现`195dfe8`：Standards静态0必须项/0单列建议；Spec4必须项（2P1、2P2）。

- P1 普通金额绕过未采用候选：候选/未完成prepare不解释为生日金额；新增写入前还核对未解决个人约束。
- P1 等待验证期间改生日cap后沿用旧预留：有原pending/占用时不开放改cap，reserve核对原金额/原operation；
  预算重试重显原确认/验证，普通恢复不生成新freeze gate。保留停止与原号核实入口。
- P2 modify读窗失败后retry不查：retry重新读取已输入候选，成功后签新交互。
- P2 写后中断原任务卡死：历史hook仍只读、返回attempt预存事实；普通当前任务恢复核对准确持久采用后给新继续交互。
  写前中断另签新候选再F10，不复用失效来源；取消/新计划/历史原响应不被恢复钩子覆盖。

整组第一次复验89 passed/1 failed/3 deselected发现BG23重显原确认前未即时绑定新预算实际remainder；
补一次公开refresh后，相关5项通过，最终整组90 passed/3 deselected。保留上述发现，不以初轮审查通过代替最终测试。

### Standards

独立子代理静态审查`8925d54...195dfe8`、修复增量`195dfe8..1c63225`及最终`1c63225..caaa5d6`：
0必须修复、0单列建议；公开契约/确认与银行事实/单目录符合，未要求无价值重构。未运行测试或访问共享库。

### Spec

独立子代理初轮4项必须修复，`1c63225`复审清零；独立局部8 passed/24 deselected，
目录`C:/Users/57652/AppData/Local/Temp/v05-budget06-spec-rereview-01`；最终`caaa5d6`增量静态确认无新增必须项。
历史hook只读，普通当前恢复给新的明确交互；最终刷新不改原pending/操作/交互，不触发银行资金写入。

两轴最终必须项均为0，分别报告，AI结果不替Erwin/Ringo本人安全批准、PM接受或实际E2E。

## CI与交回状态

[CI run 40201393209](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/40201393209)，head`1c63225`：
Repository checks显示failure，但steps为空；check-run annotation明确账号付款失败或spending limit需提高，job未启动。
这是CI Blocked，不是代码测试通过；不自行rerun，不沿用293/299的第三批例外。最终提交状态以PR实时checks为准。

代码和必要局部验证完成，E2E验收设计完成、实际未运行，停在本票交回；后续由Erwin处理实际验收/CI条件及最终合入。
不据此启动08、G3、平台01—05或改shared tracker/completion。
