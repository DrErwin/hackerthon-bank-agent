# Issue301诊断与分层验证

Status: implemented_locally / review_pending — 仅平台入口修复，未合入，真实页面S01仍Failed待新批次复验。
Ticket: [v05-cross-platform/15：完整生活目标与单项业务入口区分](../issues/15-life-goal-routing.md)
Spec: [目标与验证框架](issue301-routing-spec.md)
Base: 855497fa16616595eac8cfac9013ec701ffe942d；branch codex/v05-platform301-routing。

## 先核对原失败

已全文读取PR300固定head `31e995e75c12af57e05ae8cc9cda56b3da2d9693`的报告、manifest与gzip JSON，解压哈希95cf45a…相同。实际模型输入含完整中文原话、完整能力目录和cross.start_task；原话18字符，无替换字符。模型有效工具调用明确为subscription.cancel_subscription，invalid_tool_calls为空；HTTP202，没有网络/解析异常。
Harness按该候选查registry，以原intent_text构造StartTransferInput，未把cross改成subscription。订阅entry未类型化入口以wants_cancel原话匹配决定list/cancel；原句没有其退订动作词，所以进入list。这说明为何出现“cancel候选却盘点办结”，不证明完整目标已完成，也不在本票修改订阅解析或强制类型化该动作。

## 可证伪假设与结果

| 顺序 | 假设 / 预测 | 核对结果 |
|---|---|---|
| 1 | 平台指令把组合目标提前缩成单项：若改为按完整目标选择、保持目录和派发不变，原句及自然改写应转为cross，明确单项仍保留 | 原规则明确“盘点词与退订动作词同时出现时按退订处理”，另有动作词列表，没有完整目标优先边界；真实修前原句失败，修后原句及3种改写均正确，单项/只读/澄清与其他目标也通过。支持其为可修复的冲突来源，不据13样本声称唯一模型根因或总体成功率 |
| 2 | cross未注册/未进入目录，或其描述完全不足：若成立，当前目录不能给模型此选择 | 原输入及本次实际注册目录均有cross及减支说明。保持目录原样后路由小样全部通过，本票未证实必须跨目录补描述；不新增Cross票 |
| 3 | 程序篡改候选或原话：若成立，模型回cross但任务变subscription，或原话在入口丢失 | 原回包已是subscription；原话原样交模块。新增回放记录候选的真实组合测试，仍得到单项盘点成功、无子任务及0银行操作；这定位为候选选择与模块原话解析的组合，不是HTTP/解析故障 |

## 最小修复

仅model.py提供简短目标原则，且只在cross已注册时出现：目录支持的完整生活目标先核实、形成安排、衔接办理；明确单项/只读仍用原能力，目标不明先澄清。订阅规则去掉词表和无条件退订优先，明确查询/否定不等于退订。
不更换模型、不后处理能力选择、不硬编码原句；真实目录、proposal/派发/权限/确认/银行规则不改。没有需要本票跨目录实现的能力缺口。

## 实际命令与结果

全部在新worktree执行，Python使用现有backend虚拟环境，PYTHONPATH指向本worktree/backend；未使用其可编辑安装的旧源码。未跑全量或比较模型。

1. 修复前，`pytest backend/app/agent_platform/test_life_goal_routing.py -k full_goal_instruction -q --tb=short`：实际planner收到的指令仍含无条件退订优先，1 failed。此为指令边界替身检查，不计真实模型理解证据。
2. 修复前真实模型，同一文件`-k 'live_life_goal_routing and original' -q -s --tb=short`：1 failed，原句实际subscription.cancel_subscription，12.02秒；银行操作0/业务任务0，见[修前JSONL](../evidence/issue301/baseline.jsonl)。这是新隔离路由探针，不覆盖原真实页面失败。
3. 修后同文件 + `test_subscription_runtime.py`：20 passed、13 skipped，16.26秒（当时新文件5项替身、订阅15项）。
4. 新增未注册cross门槛后，同文件 + `test_model_planning.py test_continuation_planning.py test_cross_runtime_wiring.py test_birthday_runtime_wiring.py test_selected_entry.py`（这些文件均在backend/app/agent_platform/）：68 passed、13 skipped，28.30秒。包括真实组合子任务、养老金/生日、原转账、继续任务及模型结果校验；脚本模型不是语义理解证据。
5. 补记录候选回放测试后，同文件`-k recorded_wrong_candidate -q --tb=short`：1 passed，3.70秒，真实模块/银行组合配脚本候选，验证派发归因。
6. 修后真实GLM路由，同文件`-k live_life_goal_routing -q -s --tb=short`：13 passed、6 deselected，109.30秒（该进程在新增回放测试前已收集）。原句+3种减支改写、3种明确退订（含缺商户/明确只办一项）、2种只读查询、澄清、养老金、生日和转账均符合预期；见[修后JSONL](../evidence/issue301/postfix.jsonl)。model.py SHA256 `3d164e0cdad36fecd26972253d8c7058c2a711fb55729f41b52b540ba425e744`。

真实探针仅显式设置BANK_ROUTING_LIVE_CONFIG与BANK_ROUTING_LIVE_EVIDENCE时运行，默认跳过；配置只在本地加载，data_directory替换为每例独立临时路径，其余模型及风险事实保持。只调用真实harness.understand，不调用业务start或能力factory；模型暴露工具仍只有提议/继续/回复。每例数据库银行操作0、业务任务0；此调用路径没有银行写提交或结算，未进入确认/验证。输出只含自然输入、路由、模型名、代码哈希、耗时和零计数，无凭据/授权头/验证码。

两份JSONL及模型源码哈希见[manifest](../evidence/issue301/manifest.json)。原失败批次、修前失败和修后小样分开保存；不修改原评测期望或源证据。

## 仍未证明

本票证明了局部指令边界、实际派发归因及一次13样本真实路由结果，不是完整减支办理、真实HTTP/React页面、S02—S05、安全专业签核或PM体验接受。平台PR合入后由原E2E对话以新批次重跑S01；Issue301及E2E的最终关闭由中控按新证据判断。本票不自行合并或继承其他PR的CI例外。
