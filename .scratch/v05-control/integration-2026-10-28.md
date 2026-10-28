# 2026-10-28 最终组合持续记录

Status: automated_scope_complete_browser_blocked。执行root及本对话子代理；不是比赛提交资料或真人接受。

## 最终核查（主线51b93003）

本轮代码、修补及测试维护PR均已合并；PR355合入 `51b93003f2577f65927c66aabd38fb7d3f27836f`，只改S05旧测试断言，生产与bb6228bd相同。根Standards和独立Spec各0必须项，精确head CI因计费未启动。当前功能侧可继续按获批有限演示范围展示，完整页面验收及提交截图尚不齐，不记整版接受。

| 检查层 | 最终事实 | 证据与边界 |
|---|---|---|
| 后端原完整批 | bb6228bd：2570 passed / 1 failed / 13 skipped，2584唯一节点，exit 1，13920.37s | [无损原JUnit](evidence/2026-10-28-backend-final-original.xml.gz)，解压SHA256 `23ee3fe65fa28d8832477bf25a73f3ddd3990d68fca8304f4cf1175990d01eb6`；原失败不改名 |
| 唯一旧断言修正 | PR355：同S05与已通过邻近S01/S04共3 passed/9.42s | [固定来源与原红绿](../v05-cross-business/14-unknown-child-assertion-verification.md)。旧“结果未知/核实原操作”字词已由PR349的原child暂停说明替代；原其余11条资金/状态/部分完成/重复检查保留 |
| 后端分层去重 | 2571个非跳过节点均有通过证据，另13 skipped；没有遗留未通过的非跳过节点 | [逐节点计数及生产等价证明](evidence/2026-10-28-final-checks.json)。不是一次新的2571 passed全量；3项中2个与原2570重复，不能加成2573。除唯一目标测试外，270项backend mode/type/blob/path清单一致，SHA256 `cef00ad3e37b7b9b0f8c7cfea1099d2ee3df10f7105219c8f589964df3d8af96` |
| 模拟银行专项 | 14 passed/1.49s，同源bb6228bd | [JUnit](evidence/2026-10-28-mockbank-final.xml)，SHA256 `07cffcc688299560e2e8e8c813895f1cc772034ecab68c47da6a89d404ad0af7` |
| 前端 | 固定frontend树3fe1279c的136 passed/25.19s；既有类型检查和两种构建通过 | [JUnit](evidence/2026-10-27-frontend-final.xml)；树未变，没有重复跑；不当页面走查 |
| 链接/语法 | 仓库check_links与compileall均exit 0；新增scratch链接及diff空白单独核对 | 不把本地检查称为远端CI |
| 真实模型/接口/模拟银行 | 七个各有明确源码的局部批；最新同源普通生日跨会话/冻结后中断/取消已闭合 | [实际49行记录](freeze-recovery-http-2026-10-28.md)；不是同一commit三主线全部页面E2E，不改原Failed/暂停历史 |

13个跳过项全部是 `test_life_goal_routing.py::test_live_life_goal_routing` 的真实模型opt-in参数，原因均为 `explicit live routing opt-in only`；未在单元全量中启用，不当通过。已另运行的七批实际场景也不替代这13个路由样例。

原完整批在本工作树 `backend/` 执行，使用D盘既有venv的Python，子进程设置UTF-8、unbuffered及backend/repo的PYTHONPATH，移除BANK_LOCAL_CONFIG和BANK_PENSION_DEMO_PROFILE。命令参数为 `-m pytest -q --basetemp=C:\Users\57652\.codex\worktrees\demo-pr-merge-20261027\pytest-backend-final-20261028-01 --junitxml=../.scratch/v05-control/evidence/2026-10-28-backend-final.xml`。结束后原XML只移动到下述忽略目录并无损压缩归档，未再次跑全量。

最终原XML仍保存在本机忽略目录 `.mnemon/v05-final-checks/2026-10-28-backend-final-original.xml`，gzip解压逐字一致，压缩SHA256 `2b89e4ae5d810e9715320b0073cceed1e39e0bfdde31357de59aab712b29f75d`；没有清理失败库或重写原输出。原主目录D盘分支仍codex/docs-main、HEAD9a479ea4，仅原未跟踪原型目录，未切换/重置/清理。

剩余：CUA网址识别修复未获本人确认，26关键变体页面、200%缩放、完整读屏、真机、截图及本人安全/体验接受未完成；#160生产未知维度仍不补安全。5190真实API页面保留可复核隔离数据，运行生产与bb6228bd一致。比赛资料未制作，版本仍进行中。

## bb6228bd阶段历史

PR341最终head5810d67e已由root Standards及独立freeze_spec_review Spec各0剩余必须项；两个原must及observe停止支路闭合，精确head CI仍计费未启动。已squash合入主线 `bb6228bd6f96b8c5aaf2dd43abcd659da01bed86`；backend树81168c901697a259ff3aed231bf896dfac9902df与受测488e6fc5一致。下面旧源码失败及中止过程按历史保留，不抹去。

下文为bb6228bd执行阶段历史；完整批及唯一旧断言的最终结果以上节为准。同源mockbank专项14 passed/1.49s，JUnit `evidence/2026-10-28-mockbank-final.xml`。前端树未变，已有136 passed及类型/两构建。

[同源真实模型/HTTP冻结中断取消复验](freeze-recovery-http-2026-10-28.md)已完成：普通500元生日、S2重新确认/新挑战、真实冻结后注入快照前中断、API受控503，原号取消限定释放500元。重复原取消响应相同，银行与网关都只有一次冻结和一次释放，无订单/付款、最终冻结0。原49行、观察器重开和本机种子均保留；不是页面或完整故障矩阵。

## 已核交付

- PR353平台23已合 `bec5621800dd58ec1c24ac224fd3008bba3f0ff4`，只读当前冻结提交三态；36项局部组合通过、独立Standards/Spec均0必须项。原号银行terminal才submitted，unknown不当NotFound；CI精确head计费未启动。
- PR354 Cross13已合 `58ab51584dfd9e8dc7289eb0924594c42fe21e03`，养老金两处草稿提示扣除尚未成功的已选金额、编辑排除自身旧额、成功不双扣。固定dae4c1e3的10项通过，原红及合成夹具准备失败保留；两轴0、CI精确head计费未启动。原57行实际P01不冒称修后页面。
- [正常个人预算采用及生日实跑](adopted-budget-http-2026-10-27.md)另保留74行原始记录：原v1采用只一次、467消费、33释放、预算占用closed。其实际源码bec56218早于PR341，不借作跨会话修补验收。

## 旧组合中止与独立审查

根在未推固定源 `0fc2081eff17b3ad72af80ecb822dcd8f525cb2d` 启动Cross全目录及平台session_proof/session_recovery/release_source三文件组合。backend树 `163eac5f4b90452d1bd58dbc11a4cdfe27b77bd1`，Cross树 `dd85700ababd772139bd256cc5a59ce6dcb8d239`。

独立Spec真实复现以下两个必须修复项后，根人工停止旧组合。先精确核对python launcher与child的CommandLine均含唯一basetemp，才停止对应PID；进程exit -1。该批没有完成汇总，不作通过或测试失败结论，不与其他批相加；没有补造JUnit。临时目录仍保留在 `C:\Users\57652\.codex\worktrees\v05-birthday-session-consumer\pytest-cross09-final23-20261028-1453`。

1. P1：普通500生日上限、无个人预算，S2新确认及双因子后真实冻结成功、Cross发布前中断，取消却称没有冻结且终结，银行仍冻结50000分。独立库 `C:\Users\57652\AppData\Local\Temp\spec341-no-personal-hold-20261028-9o873sie`，原号 `166d6ed0-f5eb-4dd6-b136-01eaf2781af0`。
2. P2：有个人预算，银行明确FAILED/ACCOUNT_UNAVAILABLE后Cross发布前中断，取消与重查一直等待；银行冻结0，却保留pending占用50000分。独立库 `C:\Users\57652\AppData\Local\Temp\spec341-freeze-failed-20261028-in3ur8ey`。

两项由Cross09作者继续同票最小修补，平台353的submitted包含终态失败这一既定语义保持。成功须沿原号及原限定授权结清；失败须有真实原号失败/无效果证据才结束预算占用；未知仍暂停。根没有合入带这两项缺口的PR341。

## 63d80a02阶段复审历史

作者保存两条原红2 failed/38.09s，最小修后原两条2 passed/37.02s；新固定源63d80a02已经包含58ab5158，backend树12644938a3d43694ce1968a4a9f42302d7efc595。P1静态复核已闭合，普通_requery中的P2已处理真实原号FAILED、无回执且有failure的事实。26节点定向正在执行，未借写最终通过。

独立Spec另复现同一P2的observe恢复分支：真实银行FAILED回执在返回处丢失，Harness正常持久unknown；首次S2恢复已显示银行明确失败，随后取消和核实仍被限定finalizer拒绝，银行冻结0/订单0而预算占用unknown/50000分。证据 `C:\Users\57652\AppData\Local\Temp\spec341-failed-observe-20261028-r1o06q23\observation.json`，原号f6ba797f-17d3-4476-97d2-8a39ebca6707。作者继续把相同失败证明收尾接到observe明确停止支路，不新增资金写或放宽unknown。

先前尝试S3的探测在平台SOURCE_UNAVAILABLE被正确拒绝，未进入Cross，不列为产品失败，也不绕过来源门。当前PR341仍保持Draft，不以两条原节点转绿当作独立复审清零。

## 当时安排的后续检查（现已完成自动部分）

PR341修补固定来源后的必要定向与独立两轴、精确head CI、合入，随后同一明确源码的最终backend及mockbank检查。前端树 `3fe1279c8e17b7e3b59ee441949958085f556cd4` 未变，已有136项与类型/两构建结果不无理由重跑。新隔离模型/HTTP普通生日S2及取消故障观察另记实际来源，不以替身测试补实际证据。

5190前台与5191真实API已恢复，继续提供原已完成P01的隔离银行。CUA网址识别停线待本人手动打开5190并确认，未绕过；当前无新增截图、200%/完整读屏、真机或真人安全接受。26关键变体的实际页面分支仍按各自事实记录，不由正常HTTP主线批替代。
