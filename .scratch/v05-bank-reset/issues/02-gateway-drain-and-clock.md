# v05-bank-reset/02：整体重置的网关排空与成功时钟读取

Ticket ID: v05-bank-reset/02
Package: [v05-cross-linkage/packages/01-platform-bank](../../v05-cross-linkage/packages/01-platform-bank.md)
Spec: [银行重置接缝](../spec.md)
Type: 开发
Owner: Erwin；Codex 按中控明确分派实施
Directory: `backend/app/services/`
Status: merged — PR #325 已合入 `20d13476`；2026-10-29 核对。原验证与审查按各批记录，CI 计费未启动；实际结果与待接受项见[v0.5 完成情况](../../../docs/versions/v0.5.0/completion.md)。

原交付时状态（历史）：implemented — review/acceptance pending
Accepted by: Erwin，经本轮中控分派
Accepted at: 2026-10-27
Blocked by: [v05-bank-reset/01：受控原子银行重置与原号查询](01-bank-reset-services.md)（PR #322 已合入）
Core scenarios: [R07](../spec.md#核心场景)

## What to build

- `BankGateway.wait_for_inflight(timeout: float) -> bool`：网关自己的锁追踪所有已提交transfer/cancel_subscription/生日写（含release）future，包括排队和调用超时后仍执行者。未完False、全完True，不关闭执行器；future结束后即使失败也释放在途事实。
- `MockBankService.current_demo_logical_at: datetime | None`：只读最近成功reset的持久起点。running/failed或旧成功重放不覆盖，未成功None；不造迁移或复制时钟。
- API负责持久停收、mutation_lock和active_message_jobs；本接口不能替代准入屏障，不获取API锁，不向API暴露私有executor。

## Acceptance criteria

- [x] 转账、退订、冻结、创建订单、扣冻结、释放各自超时后仍False；等待完成后银行原号真实结果可查。
- [x] 超过4线程的排队future也计在途，不能只看processing行；等待超时不取消写，完成后网关仍可用。
- [x] future异常结束无幽灵在途，现有授权/错误协议不变。
- [x] 初始/首次running/failed为None；成功及重启读同一起点，后续running/failed与旧成功重放不覆盖，下一成功更新。
- [x] 局部及受影响services回归完成，独立分支回交中控审查；未代称整体B26或真人接受。

Verification: 全新隔离SQLite、真实ThreadPoolExecutor与可控Event阻塞，核对原号银行事实；真实模型0次，共享库不操作。

实际证据：[排空与时钟验证](../drain-verification.md)。Standards/Spec独立审查、PR合入与整体API验收待中控。
