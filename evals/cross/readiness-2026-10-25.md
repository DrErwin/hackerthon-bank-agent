# 包05准备快照 · 2026-10-25

准备增量归属 [v05-cross-e2e/01：减支核心与关键异常 E2E](../../.scratch/v05-cross-e2e/issues/01-expense-reduction-e2e.md)，关联原包05。Erwin 授权本执行对话承接，工作规格与四票记录已更新；共享交付包/项目跟踪/completion 由中控登记，本对话没有改总状态。

## 基线与交付

- 隔离 worktree：`C:\Users\57652\.codex\worktrees\v05-cross-e2e-prep\hackerthon-bank-agent`。
- 分支：`codex/v05-cross-e2e-01-prep`；准备核对基线 `25ccb96e026adbd9e74ceba9c2e28b21d364abaa`（从最新 origin/main 更新）。
- [运行入口和隔离规则](runbook.md)、[26条覆盖映射](coverage-plan.md)、[批次证据模板](batch-template.md) 已准备；01—04保留原编号、顺序和范围。
- 本轮仓库差异全是 Markdown；不创建代码PR、不运行CI、不直推main，由中控取用本分支提交。四票均未关闭。

## 实际完成的本机检查

| 检查 | 实际结论 | 限制 |
|---|---|---|
| 独立后端配置 | 已从既有本地配置复制模型连接参数；独立API/银行/管理秘密固定保存；origins为5265的两个本机主机名 | 配置被Git忽略，未显示或提交凭据；不声明模型额度/调用可用 |
| Python依赖/导入 | 复用现有venv，显式PYTHONPATH后导入路径核实位于本worktree | 未安装或修改主工作区依赖 |
| 运行时构建 | load_config、build_runtime成功；独立application.sqlite3和mock_bank.sqlite3存在 | 仅本地构建/默认种子初始化，没有发聊天或模型请求，没有启动HTTP服务 |
| 副作用基线 | 独立bank_operations行数0，模型调用0 | 默认账户/签约/历史种子创建不算业务办理；未声明正式26条种子已齐 |
| 端口 | 8165/5265本轮查询未见监听 | 尚未占用/启动，后续须重查 |
| 前端运行环境 | Node/npm可用，本worktree尚无node_modules；npm ci和Vite命令已明确 | 未安装依赖、未build、未打开页面，前序79项测试/build是前端线报告 |
| 通用Skill | to-spec/to-tickets/implement/code-review文件均存在并已读；前三项disable-model-invocation，无当前对应显式入口 | 本轮手工复用/细化批准票据，不声称调用implement；code-review按两轴子代理执行，结论见工作组review.md |

## 依赖与阻塞（本次快照，不轮询等待）

| 依赖 / 提供方 | 当前可核实事实 | 影响与解锁条件 |
|---|---|---|
| 平台11 / API线 | [PR #281](https://github.com/DrErwin/hackerthon-bank-agent/pull/281) 已合入，main含4bba921 | 不再记未合入；实际确认/验证往返仍归E2E，不继承单测为页面证据 |
| 前端01 / 前端线 | 原 [PR #282](https://github.com/DrErwin/hackerthon-bank-agent/pull/282) closed、mergedAt为空；替代 [PR #283](https://github.com/DrErwin/hackerthon-bank-agent/pull/283) 已合入e9517b8 | 不再记frontend01未合；页面/200%/读屏尚未由本票验证 |
| 账单类型化输入 / bills线（中控已另派） | cross/entry.py构造BillSummarizeInput；bills/entry.py的BillsEntry.start只接受StartTransferInput，否则INVALID_ARGUMENT。原平台05及业务01交付已披露此缺口 | XL-S01真实比较来源及XL-P读取路径blocked；需账单线交付兼容入口的票/commit及公开调用证据。未获具体新票号，保持缺口描述，不编造编号 |
| 正式种子/风险事实 / 银行、转账、安全线 | 本地构建只播默认种子；尚未核对本次两项退订、一项保留、5000入账和2500/1000适用事实 | 不先替实现侧裁定规则；按runbook提供事实/种子后先跑减支核心，再养老金 |
| 生日业务05与前端02 / 各原线 | 业务05补受控配送/结构化视图；前端02仍须前置和PM页面走查 | XL-B页面全链blocked；不绕过受控配送填原文到聊天 |
| 未知故障入口 / 平台与银行线 | 平台09记录arm_response_loss仅单测使用，B28故障装配未做 | 各写动作响应丢失变体blocked；需能在隔离真实服务中指定动作触发且不改返回为固定结果的接缝 |
| 专项/人验 / 银行、安全、PM | 银行专项、安全专项、PM体验接受、Ringo本人签核分别由原线提供实际证据 | 本轮准备与AI审查均不替代这些结论 |

未执行真实页面→模型→HTTP→银行/生活服务案例；26条全为blocked（未运行），无通过率。未运行200%/键盘/读屏/真机软键盘，当前分别blocked（等待可运行主线与对应设备/工具证据）。本轮不继承旧23条、前序单测或前序前端报告为新E2E通过。

后续由中控在账单入口和正式数据就绪时续派01；先保留完整失败批次并回原线修复，再复验。生日和全量不会因01准备完成自动解锁。
