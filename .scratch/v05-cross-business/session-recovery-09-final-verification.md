# Cross09 最终组合与唯一计数

> 以下是修补前208唯一节点的历史分层证据，未覆盖后续生产修补。
> 当前结果见[10-28收尾与精确分层验证](session-recovery-09-closeout-28.md)：
> 63d定向26过、最终488的observe与两原must定向4过，仍待根最终完整backend、
> 实际HTTP及独立两轴/精确CI。旧XML不改写，不把旧208批借写成当前源码全绿。

## 固定源码与范围

主线依赖为 `ed1596d57a5b1092a324b6d3013b1367b403cbec`（含平台18预算G3采用、
安全17/平台16原限定授权来源、平台19可信父风险原话及安全20；平台21另票不是本票前置）。
机械重基后的完整受测提交为 `895a72836f848f31a1c561b8675adc615bd508fe`，Cross 树
`298a2d3a4069adc4b1e748131ee4cc00870971ef`；与重基前 `ddb4a755` 的五提交 range-diff 全 `=`。

交审前再机械同步最新 main `aae8335394f79e30ebcabb9b57ba89cd950737c4`，对应
重基头 `c2302215c208a9e592b440e40e7b6551eeee8052`，七提交 range-diff 全 `=`。
该主线增量仅前端风险披露与根任务记录；新旧主线 backend 树均为
`02bf2c988ab52d0ffac7ac5b9e160a2802af5917`。校正测试提交 `83672967` 与重基头的
完整 backend 树均为 `0d985c1f46a5c246ff3e00dfcef51b1260d1f2de`，Cross 树均为
`4b92fed2715b8c08a21e307da2f9838d62ae9752`。后续只回填本证据文档，不变更受测 backend。

唯一一次完整组合命令（`PYTHONPATH` 明确指向本工作树 backend，解释器为既有 backend venv）：

```text
python -m pytest backend/app/modules/cross
  backend/app/agent_platform/test_birthday_session_proof.py
  backend/app/agent_platform/test_birthday_session_recovery.py
  backend/app/agent_platform/test_birthday_release_source.py -q
  --basetemp=../pytest-cross09-final
  --junitxml=.scratch/v05-cross-business/evidence/2026-10-27-session-recovery-09-final.xml
```

上面命令换行只为阅读。实际是单一 pytest 进程。数据库仅在指定隔离 basetemp；
Harness/Cross/确认/验证/模拟银行真实，规划器是明示 NoopModel 或既有脚本替身。
本轮不调用真实模型、不运行浏览器、不改写原失败演示库。

## 原完整批与单项校正

原完整批 **207 passed / 1 failed / 0 skipped / 434.66s，exit 1**：

| 范围 | 唯一用例数 | 原批结果 |
|---|---:|---|
| Cross 全目录 | 162 | 161 passed，1 个错误文案断言 |
| 平台恢复 proof / recovery / release source | 46 | 46 passed |
| 合计 | 208 | 207 passed，1 failed |

原 [JUnit 无损压缩](evidence/2026-10-27-session-recovery-09-full-before-assertion.xml.gz)
保留完整 trace，解压与原 XML 字节比较通过，SHA256
`e3343274757f9462e31f72e2127b59ade2d8b08fc7a8246db8a875eaf7ef9605`。

唯一失败是 `test_pending_personal_budget_moves_only_after_fresh_proof` 要求下一确认卡
文案含“下单”，但统一安全门的实际文案是“请完成当前操作所需的安全步骤。”。
真实 G3 预算采用、原预留、S2 fresh 恢复、新批准/验证、真实冻结及下一确认均已到达。
这不是平台18或产品执行失败，不把这条错误文案断言包装成产品缺陷。

只将该假设改成读取真实 ConfirmationRecord 并断言 `action_name == bank.create_order`
及 `session_id == S2`；原金额不变、旧编号保留与新冻结编号关联断言全部保留。
未改共享 helper、fixture、生产代码或其他207项。该测试体与提交
`83672967bdf628438b926ab4d44d125c351ec256` 字节一致。

定向复验同一个节点 **1 passed / 16.06s，exit 0**：
[JUnit](evidence/2026-10-27-session-recovery-09-final-targeted.xml)。
生产文件 birthday.py、birthday_ports.py、entry.py、personal_budget.py 与完整批受测提交
逐字相同，`git diff 895a7283..83672967 -- <四生产路径>` 为空。

**去重后208个唯一用例都有通过证据：原批207个成功 + 同一失败节点校正后1个成功。**
不把208+1加成209，不声称进行过一次新的208 passed整批；未无理由重复其余207项。
原始XML与派生的[计数/哈希摘要](evidence/2026-10-27-session-recovery-09-final-summary.json)
分开保留。根任务最后全 backend 检查仍单独记录，不能借本票冒称已经执行。

## 行为与交付边界

完整批保留真实预算专用采用、六个敏感等待的新确认/验证与真实银行链、取消、已付项不退款、
unknown/claim/active只查原号、停止后的限定收尾、断点/重启/晚回调、G2编辑与预算读取失败
暂停的断言。原09的1 fail/1 pass及后续递进失败证据均保持原样，见[过程记录](session-recovery-09.md)。

本票只改 Cross 与本组 scratch，不修改平台、安全、存储及冻结公共契约。
AI独立两轴、CI状态、真实模型/HTTP页面体验及真人接受分别记录；作者不自行合并。
