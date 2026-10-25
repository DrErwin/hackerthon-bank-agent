# 生日跨轮次边界：PR296修复后的组合复验

Ticket: [v05-cross-bank-round-attribution/01：生日跨轮次边界的真实装配归因](../../.scratch/v05-cross-bank-round-attribution/issues/01-round-boundary-attribution.md)。沿用[PR #294](https://github.com/DrErwin/hackerthon-bank-agent/pull/294)，**Depends on [PR #296](https://github.com/DrErwin/hackerthon-bank-agent/pull/296)**；296仍为Draft、未合入，294亦保持Draft。原[PR #290](https://github.com/DrErwin/hackerthon-bank-agent/pull/290)及四项strict xfail未改，原银行专项保持blocked。

## 本轮结论

**PR296的来源门已在组合中阻止已知旧订单，合法本任务订单仍可完成一次付款。** 它修的是平台付款权限接线，不是银行对象存储：裸网关在测试allow下读取/核销/释放旧对象的四项边界探针仍xfail，不能写成银行已自动增加对象轮次字段，也不能据此推断正常HTTP可越权。

本轮通过的是针对性真实装配/银行复验；没有后端全量、真实模型、外部TCP、页面E2E或真人接受。296的原1599项全量及原审查属于提供方自己的组合证据，本票没有借用为本轮全量。首批五PR批准不扩用于296/294。

## 精确来源与组合

| 来源 | 固定版本 | 本次处理 |
|---|---|---|
| main | `0930d6be59c728b9dc0ef4c4ef0b5430da12943e` | 本轮实际运行主线；已含289以及生日业务后续合入，不把296原base当作最新main |
| PR296 | `b41ef64df525d71a29e0a6c3c8f49f8a20942e01` | base main，原base SHA `31e9f2743028e25503ab5894d6af9f72856b1ea8`；head分支 `codex/v05-platform14-order-scope`；真实Git组合引入，未编辑backend |
| PR294修订前 | `eb24d739e3c3a431d34f1d164b6aca1a8cfe4470` | 原归因测试及历史事实；本次在原票/原PR更新回归断言，不新建票/PR |
| PR290 | `e9f2793bb29ec90816695ad48f8d855b16e5e9b4` | 仅从该版本取 `test_birthday_bank_eval.py`到组合工作区运行；未发布/修改290代码，文件blob严格相同 `603e31f647d95bbe378d9dde6e0eb14f7be99741` |
| 验证组合 | `577f560199a449ff9df20d6017e65025d7ad7cb3` | 独立worktree `v05-bank-294-296-verify`：main先合原294，再合296。之后只替换本组回归测试、取入290单文件；backend相对组合HEAD无任何工作区改动 |

发布的294只带 `evals/mockbank/`及本工作组材料，依赖296；验证组合不推送成另一PR。测试源码差异和最终提交在票据交付记录中固定。每次测试均使用pytest临时SQLite，不碰共享演示库。模型连接器使用既有脚本替身；D1 API建任务一次脚本路由响应，内部付款端口模型调用为0。

## 历史证据保留与断言纠正

原[不可变归因报告](https://github.com/DrErwin/hackerthon-bank-agent/blob/eb24d739e3c3a431d34f1d164b6aca1a8cfe4470/evals/mockbank/round-attribution.md)记录：D2当前任务经真实确认、双因素和执行claim，曾付款D1已知旧订单199；那是内部端口探针，未证明外部产品注入可达。[原3项通过的JUnit](evidence/round-scope-history/pr294-eb24d73-before296.xml)保留旧结果，不能当成296后的行为。

本轮先运行原294未改断言：**1 failed, 2 passed in 16.11s**。失败原因是旧测试还要求REQUIRE_CONFIRMATION，而296已返回BLOCK/ACCESS_DENIED；[原始记录](evidence/round-scope-history/pr294-eb24d73-old-assertion-on296.xml)保留，未通过删除反例追求全绿。

已把原 `test_current_task_internal_port_can_pay_known_old_order`改为 `test_current_task_rejects_old_order_and_pays_its_own_order`：确认前及执行前均拒绝旧订单、不产生确认/资金副作用；建立本任务同商品合法订单后仍拒绝旧订单；真实确认/双因素后正常支付合法订单一次，重复执行观察原操作不再扣款。旧订单保持unpaid，D1冻结仍500，D2本任务付款199后剩301。

反向检查：更新后的回归在**main093、不含296**时为 **1 failed, 2 passed in 15.18s**，因为旧订单仍能取得确认；[原始记录](evidence/round-scope-history/main093-without296-regression.xml)。说明回归能够识别缺少296的组合，不是无条件通过。

## 当前各层结果

| 层级 | 本轮观察 | 可支持的结论 |
|---|---|---|
| 旧会话/任务API | 原cookie401；D2登录后旧任务GET/resume404 | 原上游身份/任务门保持有效；ASGI TestClient，不冒充页面/外部TCP |
| 旧上下文及限定授权 | 旧ports在memory active-round门STALE_ROUND；实际SecurityGate另查为BLOCK/ACCESS_DENIED；D2读D1释放授权及B14旧操作均ACCESS_DENIED | 原旧上下文/释放授权限制保持，未靠测试allow验证 |
| 真实网关裸写 | 无processing ALLOW claim的新编号核销/释放均ACCESS_DENIED | 网关仍拒绝普通模块绕过执行器 |
| 平台订单来源门（296） | D2已知D1订单在capture_check/capture_execute均拒绝，无新确认，六类银行表不变；有本任务同商品合法订单也不能替旧订单换权限 | 原内部旧订单付款路径在本次组合已阻断；没有新增业务/安全政策 |
| 合法本任务订单 | 真实确认/双因素/执行claim，付款199一次、B14/重复观察不重复扣款；旧订单未付款 | 来源门没有把合法付款一概关掉 |
| 裸银行对象接口（290） | 原37项通过，4项strict xfail继续：B13/B22仅按用户读取、测试allow下新编号可核销/释放旧对象 | 是现有对象接口边界，未被平台修复改变；银行独立对象轮次策略仍待负责人裁定，原专项不在本票关闭 |
| 银行资金事实（290） | 500→467→33、199→301，以及四写动作回放/冲突/原号回查/原子回滚等仍通过 | 真实MockBank/SQLite事实；不是银行真实安全执行器或页面E2E的代替品 |

## 现行责任与未完成项

来源门位于[BirthdayRuntime](../../backend/app/agent_platform/birthday_runtime.py)的 `_order_source_allowed`及实际门的scope回调，核对当前任务获准create_order claim与同一原编号的B14成功订单回执，确认前/执行前/原号观察均复用。依据仍是[公共契约§6.9](../../docs/contracts/公共契约-2026-09-23.md)任务/轮次/用途资源范围和[安全附件§2](../../docs/contracts/安全与审计字段-2026-09-24.md)“无权引用不能靠补确认放行”；本票没有另造政策。

[银行附件§2/§4](../../docs/contracts/银行接口字段-2026-09-24.md)仍要求可信上下文、统一执行、归属与银行最终规则。B13/B22对象接口没有被本次改动加上round字段；是否另做银行独立来源/轮次防线，交负责人沿契约流程决定，不能把四项xfail悄悄改成通过。

main已合289，其生日单次响应丢失装配（服务端配置 `birthday_response_loss_once`、原号核实）包含在本轮5项既有生日装配回归中；不能继续沿用旧报告“生日故障装配未做”的当前结论。正式F30/F31/B26整体重置路由仍未实现，同库改配置重启仍不是重置。普通页面注入旧订单的可达性未由本票证明；真实模型、生日HTTP/页面E2E、专业安全/PM最终接受及整体跨轮次验收仍分别待对应工作线完成。

## 实跑命令与结果

组合工作区从 `backend/` 运行：

```powershell
$env:PYTHONPATH=(Get-Location).Path
python -m pytest -q ../evals/mockbank/test_birthday_round_attribution.py ../evals/mockbank/test_birthday_bank_eval.py app/agent_platform/test_birthday_order_scope.py app/agent_platform/test_birthday_runtime_wiring.py --tb=short --junitxml=../evals/mockbank/round-attribution-combined-results.xml -o junit_family=legacy
```

**53 passed, 4 xfailed in 74.96s**：本组3项、296来源门8项、既有生日真实装配5项、290银行专项37项通过；4项xfail仅来自290裸对象边界，未计通过。[组合JUnit](round-attribution-combined-results.xml)。本组单跑另为 **3 passed in 10.39s**，[单文件JUnit](round-attribution-results.xml)。没有运行后端全量。

本轮独立两轴审查与交付状态见原票。本报告不关闭安全/页面E2E、真人接受或原银行专项，294/296未获本批合入批准，不自行合并。历史CI账号计费阻塞不自动获得例外。
