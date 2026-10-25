# S01 / P01 独立案例数据与入口

归属 [v05-cross-e2e/01：减支核心与关键异常 E2E](../../.scratch/v05-cross-e2e/issues/01-expense-reduction-e2e.md) 的数据准备增量，同时为后续 [v05-cross-e2e/02：养老金核心与关键异常 E2E](../../.scratch/v05-cross-e2e/issues/02-monthly-arrangement-e2e.md) 提供同一数据格式。原 [26条设计](representative-cases.md) 与范围不变。本轮只做准备和局部验证；真实模型、HTTP、页面E2E仍未运行。

## 哪些可以直接准备

所有金额、商户和姓名都是隔离模拟银行中的虚构案例记录，依据已批准S01/P01，不是现实银行事实，也不是风险检测结论。

| 案例事实 | 实际准备 | 可观察预期 |
|---|---|---|
| 本人账户和养老金 | A1账面/可用5000元，A5本人储蓄账户0元；本月唯一入账5000元，摘要“养老金到账” | 本次资金范围5000，留1500；2500转本人A5、1000转已保存家庭联系人A4，无第三笔“留存”交易 |
| 两项可取消、一项保留 | 沿用银行原有sub_001优酷25元、sub_002网盘39元；增cross_keep通信套餐20元 | S01分别选择取消前两项、保留通信；每月未来少扣64元，已扣款不退；P01仅选择取消网盘，少扣39元不增加本金 |
| 完整比较期间 | 上月消费284元，上上月184元；三项代扣各有连续三个月记录 | 差额100元可从模拟超市消费200/100元复算，不编造“代扣涨价”；同库其他本人账户无消费可按真实空记录返回 |
| 本月已知代扣 | 本月记录25+39+20=84元，账户余额是独立的当前快照5000元 | 留存1500已含保留代扣；不重复扣历史消费、不把未来少扣39元当退款或收入 |

案例刻意不新增历史转账来伪造“熟悉收款人/惯常金额”，也不修改limits、授权、确认、风险分类或#160。

## 哪些仍需可信来源 / 安全线确认

`facts_version`、`read_fixture`、`transfer_fixtures`从已有本地配置经原模型验证后原样复制，并写规范化摘要校验。代码不添加signals/checked_signals、不制造2500/1000匹配项、不把空维度补为已检查，也不生成风险等级。

- 已有配置的事实若不适用本轮动作/账户/金额，仍是缺口；复制成功不等于可批准这笔动作。是否接受既有演示事实的来源与适用范围交中控/安全线记录，不能由本数据工具签准。
- 没有2500/1000动作事实时，保持原安全门暂停；用户说“养老金”也不能被改写成白名单话术来绕过检查。当前转账模型之外的文本处理是否覆盖联动子任务，需安全/平台线核实。
- 银行种子只能证明账户、入账、签约和历史消费，不能证明设备熟悉、没有屏幕共享、没有受胁迫等未观测环境。若需要改变这些未知维度的处理方式或给予新增放行条件，是安全语义选择，须PM和安全线裁定；本线不改#160、不提“未知按低风险”方案。

因此：**数据ready，风险未授予**是合法准备结果。即使所有种子已齐，也不得宣称S01/P01可完整通过。

## 准备和启动

固定前端修复基线main `9a479ea`（含#286的代码提交25ccb96）。本工具只向当前worktree的`.mnemon/v05-cross-e2e/<case>/<run-id>/`写入新目录，不接受任意数据库路径；旧批次存在即拒绝，绝不重置共享演示库。每个场景新批次；恢复必须用原目录和秘密，不能再次prepare。

从此worktree根目录运行，使用已有后端venv但显式指向本worktree源码：

```powershell
$env:PYTHONPATH = Join-Path (Get-Location).Path 'backend'
$casePython = 'D:\hackerthon-bank-agent\backend\.venv\Scripts\python.exe'
& $casePython evals/cross/case_runner.py prepare XL-S01 --config .env.cross-e2e.json --run-id s01-data01
& $casePython evals/cross/case_runner.py prepare XL-P01 --config .env.cross-e2e.json --run-id p01-data01
```

本地源配置可换成现有后端配置文件，仅读取连接参数和已有风险事实。新配置位于各案例的`.env.case.json`（受`.mnemon/`忽略），API签名/银行/管理员秘密另生并固定保存；不提交、打印这些值。`manifest.json`记录业务时钟（与银行相同UTC+8）、种子哈希、风险配置摘要和预期，初始model/http/page_e2e均not_run。

前置就绪后（本轮未执行），先检查8165/5265空闲，在单独终端启动：

```powershell
& $casePython evals/cross/case_runner.py serve --directory .mnemon/v05-cross-e2e/XL-S01/s01-data01 --port 8165
# P01执行时先停本轮S01进程，改用P01目录；不可两个案例共用同一个库。
```

前端在本worktree的`frontend/`运行`npm ci`后：

```powershell
$env:VITE_API_PROXY_TARGET = 'http://127.0.0.1:8165'
npm run dev -- --host 127.0.0.1 --port 5265 --strictPort
```

用户页`http://127.0.0.1:5265/`，管理页`http://localhost:5265/admin`；选择real-api模式，source配置origins在新副本中固定为上述来源。停止仅停止自己的进程。更换前端端口须另行核对origins，不能借用他人服务。

**必须使用case_runner的serve入口**：普通local_demo启动会额外播入默认工资6200元，不能作为本次5000元唯一入账的案例。case_runner只在构建运行时期间替换`seed_flow_history`的初始化数据，写入真实独立银行库；构建结束立即还原方法，再由原模型/HTTP/确认/安全门/模拟银行规则处理请求。没有mock模型输出、银行响应或安全决策。重复启动只INSERT OR IGNORE，不覆盖已取消签约、余额、原操作与检查点；种子/风险配置变化则需新批次。跨业务月份应重新prepare新批次，不能把旧月种子当本月事实。

## 准备阶段历史缺口与当前状态

1. 原账单类型化输入及平台旧断言已由PR #284/#292合入；固定2a070b9不再以此为未合入阻塞。
2. 以下为原准备阶段发现，已随PR #297合入修复；不再作为当前未交付：P01本人A5不是保存联系人：当前pension只从`transfer.list_payees`选去向，再以`SavedPayee`提交；真实联系人中没有A5。需cross业务线补本人账户去向，不能在本评测工具把A5伪造为联系人。
3. 原准备阶段入账适配缺口已随PR #297合入；以下保留原发现：P01入账读取：正式`BillDetails.transactions`沿用银行字段`direction="inflow"`、`nature="transfer"`；当前`PensionFlow._income_transactions`只认`transfer_in`，与真实契约不符。需cross业务线修复；不能在fixture中造非法direction或改成按余额来替代原场景。
4. 适用风险事实与文本处理仍按上节交安全/平台线核实。上述2/3是既定业务的接入缺陷，不是需要PM重定业务规则；具体修复票由中控关联/分派，本线不越界。

实际运行时仍须从自然表达开始、逐项确认、保留父子任务/原操作/确认与银行次数，保留失败批次；本工具仅提供数据和服务入口，不是自动页面执行器或E2E报告。PM接受、真人安全签核、局部测试、真实模型、HTTP、页面和体验专项分别留证。

2026-10-25已正式启动E2E01，S01首批实际失败在模型入口选择，见[失败证据](evidence/2026-10-25/s01-live-20261025-01.md)。不是上述账单/平台未合入，原失败未被准备/局部成绩替代。
