# 银行专项发现：跨轮次旧对象仍可使用（测试授权边界）

转给: Erwin（中控分派平台/安全核对；可能需要 services/storage 单目录票）

Source ticket: [v05-cross-bank-eval/01：银行事实和防重专项验收](issues/01-birthday-bank-evidence.md)。

Status: open — 2026-10-25 独立 Spec 子代理发现并实跑复现，未修公共实现，未裁定新业务/安全规则。

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
