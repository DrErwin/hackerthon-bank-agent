# 银行专项发现：跨轮次旧对象仍可使用（测试授权边界）

转给: Erwin（中控分派平台/安全核对；可能需要 services/storage 单目录票）

Source ticket: [v05-cross-bank-eval/01：银行事实和防重专项验收](issues/01-birthday-bank-evidence.md)。

Status: open — 2026-10-26 只读核查与责任判断完成：释放收尾链路有明文（M14/安全§3.1），B13/B22/B11 对象层补轮次属防御纵深决策（待 Owner 确认）；产品路径上游门已覆盖（#294/#296），银行对象层缺口由存储/服务两票候选修复，评测收口另票。未实施，未获目录窗口。

2026-10-26 核查入口：[v05-bank-round-objects 核查与责任判断](../v05-bank-round-objects/verification.md)。

## 原要求与证据

[包06](../v05-cross-linkage/packages/06-bank-eval.md)要求“错误用户/账户/轮次……不能绕过原银行规则”。已通过的 MB-B06 证明同库原操作编号及 B14 的用户/轮次限制；新建数据库也能隔离旧资源。这两种证据不能代替“同库换轮次、新编号用旧对象”的检查。

探针只用独立临时 SQLite、真实 BankGateway/MockBankService/MockBankStore，固定银行时钟和显式测试授权回调；没有真实安全执行器，不能据此断言实际 HTTP/产品入口可越权。

最小复现：

1. 同库 `TrustedContext(user_id=U1, demo_round_id=D1)`；从 EVAL_A 冻结 500 元并创建花199的未付订单。
2. 保留 user，仅把 context 的 demo_round_id 改为 D2；测试授权仍允许银行调用。
3. B13/B22 读取旧 freeze/order 均返回 ok。
4. D2 用**新** UUID 核销旧 freeze/order，可成功消费199；另一个独立探针中，D2 用新 UUID 释放旧 freeze，可成功释放500。

四项探针在[评测文件](../../evals/mockbank/test_birthday_bank_eval.py)的 `test_old_round_objects_with_new_operation_are_denied`；每项独立种子。用 `--runxfail` 可看到未满足的断言，不进行任何共享重置：

```powershell
cd backend
$env:PYTHONPATH=(Get-Location).Path
python -m pytest -q ../evals/mockbank/test_birthday_bank_eval.py -k old_round_objects --runxfail
```

默认以 `xfail(strict=True)` 保留：这四项是**未满足**的要求，不计入通过；未来修复导致 XPASS 会让专项失败，要求人工复核并移除已解决缺口，避免长期吞掉修复。

## 提供目录及建议依赖

- `backend/app/services/`：网关 B13/B22 只传 user_id；银行冻结/核销/释放及订单对象查找按 user_id；新写动作只将自己的 UUID 绑定当前 round。
- `backend/app/storage/`：冻结/订单事实目前未与原 demo_round 建立可查询的对象归属；是否补字段/迁移由提供方判定，评测不复制规则。
- `backend/app/agent_platform/`、`backend/app/security/`：核对真实运行环境的轮次生成、旧任务/资源失效及授权绑定，决定银行应独立拒绝还是已有上游门承担；先给出符合原规则的责任判断和可检查证据，不由本票擅定新规则。
- 由中控按一票一目录指派必要修复；包05补真实运行环境的跨轮次全链检查。本票仍可交付已通过银行事实，完整跨轮次验收保持 blocked。

## 2026-10-26 责任判断与最小票

核查时点 main `38b3b81`（运行代码同 `5347dd7`）；01:34 起 origin/main `5b652e1`（仅 `.scratch/v05-cross-frontend/` 走查文档，无运行代码差异），01:50 起含本组核查/票据提交。核查结论：

- **产品路径已覆盖**：旧轮次会话 401、旧任务 GET/resume 404；真实安全 claim/旧释放授权拒绝；平台订单来源门（PR #296，`620746a`）拒绝跨任务与旧轮次订单；B13/B22 不是模型工具、无 HTTP 路由。四项探针只经显式测试授权，**不能写成产品可越权**。
- **责任分层**：释放收尾链路有明文——公共契约 §9 M14 把“错误用户／冻结／**轮次**拒绝”列给 cross+security+mockbank，安全附件 §3.1 明确“银行仍校验可信主体对原冻结的释放权限”；B13/B22 读取与 B11 核销只有归属语义（银行附件 §2/§4/§9.3/§11）+ 包06验收第4条，把轮次纳入对象归属是**防御纵深实现决策**，不是契约字面要求。规范的轮次切换是 B26 重置（清冻结/订单），当前 F30/F31 未实现；四项探针的“同库换 round 不重置”不是规范支持方式。选择补对象归属而不是改评测适配平台门，需 Owner 确认并记录。
- 平台核对普通请求轮次的依据是公共契约 §6.4/§6.5/§6.3；§6.9 只讲 `ResourceRef` 资源读取，不能当银行对象前门。
- 实现层不一致：`bank_operation_scopes` 自 v0.3 起按 `(user, round)` 绑定操作编号、B14 按轮次拒绝（契约只要求编号绑定身份）；对象没有轮次属同一银行服务内的实现不一致。
- 复跑确认（隔离临时目录）：`--runxfail` 四项仍 4 failed；组合基线命令 `test_birthday_round_attribution.py + test_birthday_bank_eval.py + app/agent_platform/test_birthday_order_scope.py + app/agent_platform/test_birthday_runtime_wiring.py` = 3+41+8+5 = 57 节点，实跑 **53 passed, 4 xfailed in 83.82s**（2026-10-26；与 `evals/mockbank/round-attribution.md` 记录一致）。
- 修复票（待 Owner 决策后）：[存储 01](../v05-bank-round-objects/issues/01-object-round-storage.md) → [服务 02](../v05-bank-round-objects/issues/02-object-round-services.md) → [评测收口 02](issues/02-round-object-regression.md)。storage 当前正被生日线（`codex/v05-birthday-immutable-checkpoint`，`3e38506`/`c886660`）使用，须等其合入并 rebase；不做共享库迁移，旧 v4 含对象行库按既有先例明确拒绝加载。
