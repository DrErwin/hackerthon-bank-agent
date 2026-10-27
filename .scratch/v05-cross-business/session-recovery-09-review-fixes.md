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

## P3：提交正文

最终仅补 `656439d3` 与 `cfc039cb` 的 why 正文，保留所有文件树字节；使用
精确远端 head 的 force-with-lease，只重写本分支，另存旧新映射及树等价证据。
