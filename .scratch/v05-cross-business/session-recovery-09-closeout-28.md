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
