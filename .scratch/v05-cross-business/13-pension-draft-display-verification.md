# Cross13 定向验证（2026-10-28）

Ticket: [v05-cross-business/13](issues/13-pension-draft-display.md)
Spec: [两处草稿额度提示](13-pension-draft-display-spec.md)
Status: implementation verified locally; independent review and merge pending

## 固定来源与差异

- 基线 `bec5621800dd58ec1c24ac224fd3008bba3f0ff4`。
- 原提示红例 `f2794d7f8193d9898d391ffb2fc7d57b3f2e0fd5`：生产仍为基线，仅先新增本票规格与公开提示回归。
- 生产修补 `f202ce349c30a0d11499bba632ea1b3a91b800f1`。
- 最终受测来源 `dae4c1e3b5c5d9b21224828bbab72e647ef5a0c9`；相对上一项只修正合成恢复测试的保存线程名。
- 最终受测整树 `3063e7e9533a80546875e09ac371ade80c135c3a`；Cross 树 `a74e42bffd58e320b73c3dca21ca11ffdf14e504`。
- 受测生产 blob `21310e1e0051f01fa3cc6431745ac4d2c25959f7`；新测试 blob `a1d515d6d7625b1946dc6550067d37c7e58f6d06`。

生产仅增加草稿呈现计算，供 destination 与 amount 两处提示读取。AST 核对原有方法中只有这两个提示方法改变；`_remaining`、`_preflight`、`apply/apply_text`、`_adopt` 与其余原有方法未变。原 `test_cross_pension.py` 文件及全部原断言与基线逐字相同。

原真实 P01 的57行附件仍来自 `5278f870`，未重跑或改写；其中26/27/28行的旧提示与29行正确的最终合计分别保留，不把旧附件称作修补后的页面结果。

## 实际批次

所有 XML 原始字节无损 gzip 归档，mtime=0；原 XML 与各批新建的隔离 pytest 目录保存在此工作树旁 `cross13-local-evidence/`，未复用或清理旧批。完整 node、来源、原文件位置及原始/归档散列见[证据索引](evidence/13-pension-draft-display-index.json)。

| 批次 | 结果与控制台耗时 | 解释与原始附件 |
|---|---|---|
| red01 | 1 failed / 10.90s | 真实公开提示回归：选2500后仍显示3500；[原始XML归档](evidence/13-pension-draft-display-red01.xml.gz) |
| green01 | 1 passed / 7.67s | 首个用例在工作文件修补后转绿；父提交f2794d7f，生产文件SHA256 `999ac859911a7f37f5f49be212a5a68e9dd5e525462dfa83df1c1190dc961fb1`；[原始XML归档](evidence/13-pension-draft-display-green01.xml.gz) |
| targeted-final01 | 7 passed / 3 failed / 28.19s | 固定f202ce34。三失败均是新增合成恢复夹具误用业务task名读取受控保存线程，尚未执行目标断言；不是产品失败。不改生产，改用公开saver.thread_id；[原始XML归档](evidence/13-pension-draft-display-targeted-final01.xml.gz) |
| targeted-final02 | 10 passed / 25.00s | 固定dae4c1e3，同一10节点集合全部通过；[原始XML归档](evidence/13-pension-draft-display-targeted-final02.xml.gz) |

最终 XML 的 suite time 为24.806s，控制台总耗时25.00s；不把两种计时混写。解压后 SHA256 `0d5da8d4d891fe4c49c57d0d0bff3049c2d08810042b903d7a692f2a5218eb5b`，gzip SHA256 `d6212a2079d4ebdf59818ef344c583a98d06e97020c75d1174195fd9e0caddf9`。

## 节点与范围

新文件4节点：正常公开开始/续做看到3500→1000→0，最终采用合计仍3500；原当前笔已有1000的合成恢复问题显示1000可重分配，改900后显示100；较早2500笔分别处于未提交、明确失败、已成功时，当前笔旧额不重扣、成功事实只算一次。

原文件6节点：P01两笔正常、已知代扣是否包含于留存、原金额超范围重问、转账前余额刷新、失败暂停后续、第二笔未知保留原安排。最终命令为：

```text
python -m pytest -q backend/app/modules/cross/test_pension_draft_display.py
  backend/app/modules/cross/test_cross_pension.py::test_p01_income_basis_reserve_and_two_transfers
  backend/app/modules/cross/test_cross_pension.py::test_p03_known_debits_calibration_changes_protection
  backend/app/modules/cross/test_cross_pension.py::test_reserve_over_base_and_amount_over_remaining_are_refused
  backend/app/modules/cross/test_cross_pension.py::test_f1_balance_refresh_before_each_transfer_gates_the_second
  backend/app/modules/cross/test_cross_pension.py::test_f3_a_failed_transfer_pauses_the_remaining_ones
  backend/app/modules/cross/test_cross_pension.py::test_p06_unknown_second_transfer_keeps_the_arrangement_open
  --basetemp <本工作区旁新建的targeted-final02目录> --junitxml <原始XML路径>
```

这是本地 CrossEntry 提示与流程分支验证，复用原有明示契约替身；恢复状态是通过公开 saver 准备的本地合成夹具，不代表产品新增编辑入口，也不代表一笔真实银行成功。没有模型、HTTP、浏览器、共享数据或全量运行；不改变金额接受、预检、确认验证、安全profile或银行规则。独立两轴、CI状态和合并交中控处理。
