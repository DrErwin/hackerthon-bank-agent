# Cross09 独立审查后的恢复断点

范围仍为 `v05-cross-business/09`、Cross 目录与本组 scratch。原 208 唯一节点
证据及原始 XML 保留，本次生产修补不借用旧整批作为修补后的通过结果。

## P2：预算读取失败不能丢失原付款目标

确认接缝是已有真实 Harness/G3 专用预算采用、恢复、确认/验证及模拟银行。
受测生产 `ea8da3da4e6e24255410cba56add9e377b82c30b`：原 capture 确认等待，
新会话 fresh 恢复时让真实银行 `list_transactions` 返回 BANK_UNAVAILABLE，
恢复读取后选择“重新核对预算”。单商品必须重新展示 `bank.capture_frozen`，
仍对原 `order_id` 付款；双商品必须先付原订单再办理下一件。两个原等待阶段
（确认/验证）均须新确认、新版本、新会话，原订单、金额和历史不变。

首个单商品确认等待红例 **1 failed / 17.08s**：预算重试错误返回 SUCCEEDED，
原订单已创建但未付款，500 元未消费冻结被释放。原失败 XML 无损保留为
`evidence/2026-10-27-session-recovery-09-review-capture-before.xml.gz`。

当前优先解释是 fresh 清 pending 后丢了稳定 capture 目标，预算重试从订单
总推进继续；预算参数漂移及平台替换到错误订单不符合已核实的暂停前原订单
不变事实。最小修补在 Cross 保存尚未重新核对完成的 fresh 稳定目标，重试
先回该目标的公开核对，成功取得新门后清除，不缓存旧卡或复用旧验证。

修补后四组合（单/双商品 × 原确认/验证等待）**4 passed / 85.12s**，
原失败节点未删、原终态断言未降级。均先显示原订单的新 `bank.capture_frozen`
确认，再以真实新验证付款并完成全部原商品；下单数量没有增加。
JUnit：`evidence/2026-10-27-session-recovery-09-review-capture-after.xml`。

## 待核：新冻结写成功、Cross 快照前异常后的取消

须经真实 Harness/G3、已采用个人预算、新会话 fresh、新确认及新验证，让
新 freeze_execute 实际完成后抛错，再由真实恢复/取消接缝证明可达性。
未跑通该链前不把静态 `operation_ids[0]` concern 写成产品失败；不以直接
调用写端口并伪造快照替代真实链。

真实链现已复现 **1 failed / 18.22s**，原生产 `f7204bdc`（只含上面的
capture 修补），JUnit `evidence/2026-10-27-session-recovery-09-review-freeze-before.xml.gz`。
新确认、新验证后，新冻结真实成功，紧接着在 `freeze_execute` 返回后抛 OSError，
Cross 的 G3 published_ref 和旧验证快照未变。新的 cancel 实际可执行，返回
CANCELLED；银行新冻结仍有 50000 分，旧操作 not_found，个人预算占用已关闭。
这证明漏核实实际新冻结，但不是静态假设里的 `intent` 可见状态：该 intent
只在缓冲中，故单改历史首项为末项不够。

两条先前探测错误分别保存、不算产品红例：

- `...-review-freeze-test-shape-error.xml.gz`，1 failed / 15.23s：测试作者
  把 OperationFound 当 OperationResult，读取形状错，尚未检查取消。
- `...-review-freeze-barrier-assumption.xml.gz`，1 failed / 16.86s：错误假设
  中断后有持久 pending 会拒绝新 cancel。实际 result=None 时没有该持久
  转换，新的 cancel 能进入。更正测试为核查真实银行剩余金额后取得上述红例。

最小待核公开能力：`requery/bind_freeze == None` 既可能没 execution claim，
也可能 claim 未决或银行不可读，不能据此宣称未提交。已向平台 owner 报明：
取消无冻结快照的 pending hold 时需对准确末项原操作查只读提交事实；明确未
提交才关闭，已完成绑定原冻结并按原授权收尾，未知保留占用。Cross 不读私有
claim、平台 snapshot 或伪造 bank proof。确认现成能力或提供接缝后再消费。

## P3：提交正文

最终仅补 `656439d3` 与 `cfc039cb` 的 why 正文，保留所有文件树字节；使用
精确远端 head 的 force-with-lease，只重写本分支，另存旧新映射及树等价证据。
