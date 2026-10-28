# Cross09：10-28独立Spec后冻结取消闭环

目录仍为 `backend/app/modules/cross/` 与本组 scratch，沿本票/分支/PR #341。
旧 `0fc2081eff17b3ad72af80ecb822dcd8f525cb2d` 的 after23 11 passed 原XML
保留；根任务启动的完整组合因已确认 must 被精确终止，exit -1、未完成，
不记为通过、失败或最终全量。原隔离库保留。本轮依中控要求只做必要定向，
最后全backend由根任务统一运行。

## 新的两个真实红例

受测生产 `0fc2081e`，backend树 `163eac5f4b90452d1bd58dbc11a4cdfe27b77bd1`。
新测试通过真实Harness/G3/确认/code/mock-face/模拟银行；规划器为明确替身。

1. G3专用采用个人预算，S2 fresh新冻结确认及验证后，将本测试独立银行A1
   设置closed，银行真实返回原号FAILED/ACCOUNT_UNAVAILABLE、receipt=None；
   freeze_execute返回后抛OSError、Cross快照未发布。cancel仍WAITING_INPUT，
   原pending占用50000分无法关闭。
2. 普通500元生日上限，无个人预算记录；S2 fresh确认/验证后原号真实冻结成功，
   同断点抛OSError。cancel错误返回CANCELLED但银行剩余冻结50000分。

合计 **2 failed /38.09s**，JUnit原字节无损保存为
`evidence/2026-10-28-session-recovery-09-closeout-before.xml.gz`。不把测试中
明确的隔离A1closed夹具操作写作新银行规则，不修改Spec原失败临时库。

## 最小修补边界

- 清pending前在Cross自己的持久状态保存当前freeze原号；无个人预算也保留。
  有占用时只用准确当前/末项原号，仍走353公开三态，不读平台私表/默认命名空间。
- submitted之后沿原号bind/requery。只有真实OperationResult同op、冻结类型、
  FAILED且无receipt/有failure证明没有效果时才结束取消及关闭已有占用；
  不调用银行release/新freeze，不把not_found/unknown/读取失败当失败。
- 未决标记在暂停和重启中保留，预算候选/上限修改入口不能绕过原号核实。
- 成功继续原号绑定与原有限finalize；重复cancel不再产生任何新写。

红绿、精确source/tree/JUnit及去重计数在本文件续记。原208批、原after23
11批及此前全部失败均不覆盖、不冒称本轮源码完整通过。

首个最小修补后原两节点 **2 passed /37.02s**，JUnit
`evidence/2026-10-28-session-recovery-09-closeout-after.xml`：FAILED分支不
释放、不重冻，有预算的原占用关闭；无个人预算成功分支沿已保存的准确原号
限定释放到零。两者重复cancel均无新增写，原银行操作回执不变。

## 固定63d的定向及observe剩余P2

机械同步主线 `58ab51584dfd9e8dc7289eb0924594c42fe21e03` 后固定源码
`63d80a0219829fe7196e5c380132dc95ad9792f4`，20提交range-diff全`=`，本票
生产和故障测试blob与重基前 `60c69da9` 相同。backend树
`12644938a3d43694ce1968a4a9f42302d7efc595`，Cross树
`9fbc933644333880c9281767c79532ae10e9d001`。

必要定向 **26 passed /445.45s，0 failed/error/skipped**，
`evidence/2026-10-28-session-recovery-09-targeted.xml`，SHA256
`bb9e6a284caaf1f905d720da51479810084db6a6992313590f26d228b10b2f4e`。
覆盖capture5、预算/无预算成功/FAILED/未知/重启/重复、旧取消/已付及六等待。
本批不是完整Cross，不覆盖后续observe修补；不得借写成最终完整全绿。

独立Spec新增正常入口：真实银行FAILED回执已保存，在网关返回点抛OSError，
执行器发布unknown_freeze；首次S2恢复只读核实到原冻结FAILED，保持原占用。
用户明确cancel并原号核实后却RUNNING、FREEZE_FAILED阻止释放，占用仍50000分。
作者同真实链复现 **1 failed /26.58s**，原生产仍63d，原XML无损保存于
`evidence/2026-10-28-session-recovery-09-observe-failed-before.xml.gz`。
这不同于未通过平台SOURCE_UNAVAILABLE的S3探测，不绕平台来源门。

拟只复用当前严格原号冻结FAILED/无回执/有failure证明到observe的明确停止
支路：被动观察不关闭占用、不继续购买；明确停止且银行证据完整才close已有
占用并取消。unknown/读失败保持原号等待，不调用任何银行写。根main后续
`7d029a5d`仅docs、backend与58ab相同，不额外重基或重跑26。

## observe修补与最终定向

最终执行源码 `488e6fc59234dcf76f8aa691f3442c757e9209b8`，backend树
`81168c901697a259ff3aed231bf896dfac9902df`，Cross树
`733ccf249143832ba831e6ae73cff1e08b0c4197`。只抽出已有的严格原号失败证明
供requery与observe明确停止复用，不动353、安全或银行规则。

被动observe仍保留原占用；用户明确停止后再次按原号读取，只有真实同op/
bank.freeze_funds/FAILED/receipt=None/有failure时关闭占用、取消任务。
银行读失败仍待核实；没有release、重冻、下单或核销写。内部银行code继续
保留在原OperationResult，用户只看到业务资金事实。

单批 **4 passed /74.02s，0 failed/error/skipped**：

- 正常FAILED响应丢失→unknown→首次S2只读observe→明确停止。
- 同入口在明确停止时银行暂不可读：占用原样保留，恢复读取后原号结束。
- 两个原must复核：有预算真实FAILED、无预算真实成功冻结再取消。

所有分支都断言原银行回执和操作号不变、重复cancel无新增写；观察本身不
关闭占用或继续购买。JUnit：
`evidence/2026-10-28-session-recovery-09-observe-failed-after.xml`。

命令使用 `test_birthday_freeze_closeout.py::test_explicit_stop_closes_the_observed_original_failed_freeze`
的两个参数节点与 `test_cancel_reconciles_the_exact_bank_terminal_freeze` 的
`budget-failed`、`no-budget-succeeded` 两节点，隔离basetemp为
`../pytest-cross09-observe28-green`，没有重跑26或完整Cross。

26批属于63d，4批属于488，两批交集2、去重28个节点，但**不宣称28个节点在
最终源码一次全通过**，也不将26+4算成30。最终完整backend/实际HTTP及独立
两轴/精确CI另由根任务收口。本票不自行合并、不写真人接受或安全真人签核。
原XML及所有失败保留；最终只补本组scratch，backend树保持488原样。
