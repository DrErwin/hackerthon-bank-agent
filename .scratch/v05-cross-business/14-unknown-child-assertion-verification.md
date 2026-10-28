# Cross14 局部断言维护证据（2026-10-28）

Ticket: [v05-cross-business/14](issues/14-unknown-child-assertion.md)
Spec: [S05原子任务公开暂停说明](14-unknown-child-assertion-spec.md)
Status: local verification complete; independent review/CI/merge pending

## 来源与维护范围

基线 `bb6228bd6f96b8c5aaf2dd43abcd659da01bed86`。仅修改 `test_cross_expense.py` 的既有 S05 用例：原两条旧话术断言改为核对 `OPERATION_UNKNOWN`、原子任务公开 message、未获银行最终确认、勿重复操作、可继续查询及处理完成前不继续其他项目。原子任务 needs_attention、父任务 RUNNING、重复续做不重派发、成功银行调用、停止后部分完成、已成功退订与节省金额的另外11条原断言按原顺序完整保留。AST核对同文件其余函数/类逐字结构不变，未改夹具或辅助函数。

生产代码无变化；沿已合PR349 PC01-PC03核对，未把所有 needs_attention 重新称为银行结果未知。

## 实际红绿

| 批次 | 固定source | 结果 | 原始附件 |
|---|---|---|---|
| red01 | `20a0fe5d27bbfb71f9c976f6f1cdc3ee53d4b4ac`，测试及生产与基线相同，仅新增本票简规格 | S05 **1 failed / 12.60s**，仍断言旧词“结果未知”；子任务recovery_reason实际为OPERATION_UNKNOWN | [无损XML](evidence/14-unknown-child-assertion-red01.xml.gz) |
| green01 | `c78992ffc503bc93d758807afd74d5858d52c081` | S05、S01、S04 **3 passed / 9.42s**，0 failed/error/skipped | [无损XML](evidence/14-unknown-child-assertion-green01.xml.gz) |

最终受测测试 blob `f968e4486914de502ad3d57ba7e35498f576a6aa`；整树 `0ec985d984b0c241047ccf83a44b596f8ce18999`；backend树 `40fd184bf2a622350bc2e3dc65e96bf169e8498b`。最终提交仅继续归档本票文档/证据，backend树与受测版本保持相同。

green XML suite计时9.234s，控制台总耗时9.42s分别记录；解压SHA256 `d48d12e02e61e957580f9f08261352abd07e08b7f4df26d53467a26d481c8ad3`，gzip SHA256 `a3c697e4cfe2b669ce4fc113515bd677e27adb0ba00740973cf4e3a3ced0b111`。

red解压SHA256 `385af17d2206a86e03517d97248a11b974f2e0e6a072745bce14c9ee6b97e8ad`；所有原XML、节点和归档hash见[索引](evidence/14-unknown-child-assertion-index.json)。gzip无损/mtime=0，解压逐字核同；新建隔离basetemp在本工作区旁 `cross14-local-evidence/red01` 与 `green01`，原XML与数据库保留，未复用旧目录。

## 后端生产等价证明

backend整树包含测试文件，所以基线树 `81168c901697a259ff3aed231bf896dfac9902df` 与上述受测树不同。为精确核对生产，比较 `git ls-tree -r --full-tree REV -- backend` 的原始行，仅剔除唯一目标测试路径 `backend/app/modules/cross/test_cross_expense.py`，保留Git顺序，以LF连接并保留末尾LF：

- 基线与受测版本剩余 **270项** mode/type/blob/path逐字一致，包含所有生产代码和其余测试。
- 两份清单SHA256均为 `cef00ad3e37b7b9b0f8c7cfea1099d2ee3df10f7105219c8f589964df3d8af96`。
- 相对基线只有这一份backend测试发生差异，没有其他后端文件变化。

## 根全量与本票结果分列

根原全量仍为bb6228bd：**2570 passed / 13 skipped / 1 failed**。根XML只读复核SHA256 `23ee3fe65fa28d8832477bf25a73f3ddd3990d68fca8304f4cf1175990d01eb6`，未复制、修改或覆盖；本票三节点结果独立记录，不组成另一次全量通过。

本地组合沿原PlannerStub、FakeSubscriptionBank及受控子任务执行，均为明示测试替身；没有真实模型、HTTP、浏览器、共享库或全量运行。独立规范/规格审查、CI核对与合入交root，作者不自行合并或代签接受。
