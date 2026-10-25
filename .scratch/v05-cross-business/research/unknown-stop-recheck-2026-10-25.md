# 冻结未知后停止：PR #288 + #289 紧急组合复核

Status: verified — PR #288 已有停止修复覆盖，不新增业务票或修复 PR。

来源：运行装配线独立 Spec 的 P1 材料
`v05-runtime-risk/.scratch/v05-cross-platform/research/birthday-unknown-cancel-gap-2026-10-25.md`。
本轮由中控续派，预算持久层与共享跟踪不在范围内。

## 固定输入版本

- PR #288 最终业务版本：`8ea7042e77e1bad5042cfc1061f4c52b9020d3ff`。
- 平台 PR #289：`18a3f39bf137f26909b2bd1451a76f6958cd1920`。
- 临时组合提交：`66d3e89ae8c6d0c3f99e225037a61b573f0c33da`，两个父提交分别为上述 #289、#288。
  管理 worktree `v05-birthday-stop-check`，分支 `codex/v05-birthday-stop-check`；不推此组合分支、不合并原 PR。
- 已核对组合 checkout 的整个 `modules/cross` 与 #288 无差异，`agent_platform` 与 #289 无差异。

## 结论与已有修复位置

旧材料的业务基线没有 #288 的停止修复。#288 在 `birthday.py` 的冻结、订单、付款回查成功后
均检查已保存的 `stop_reason`；已停止则转 `_finalize`，不会进入新订单或付款。
收尾会保留停止原因、清除旧确认/验证，并在未知操作仍在途时只给原操作核实入口。
本轮没有改动生产代码，仅补本票组合回归探针和证据。

## 同一个探针的旧版对照

在组合 checkout 中只将 `birthday.py` 临时换为 PR #289 上尚未含 #288 的旧版本，其余组件不变；
运行 `test_stop_survives_unknown_original_lookup_on_real_ports` 的 freeze_funds 用例。

实际 **1 failed, 2 deselected in 19.70s**：银行冻结已发生，取消、重建 entry、刷新新菜单、
沿原编号回查之后返回 `waiting_approval`，预期 `cancelled`。这与来源材料的原症状一致。
对照运行后立即恢复 #288 的原始文件；无源码改动残留，不将对照文件提交。

## 公开 entry 与真实 ports 回归

探针：[test_unknown_stop_combination.py](test_unknown_stop_combination.py)。
显式在组合 checkout 上运行，不加入单独 #288 的普通后端收集范围：限定释放还需要 #289
核实原执行 claim，不能把组合测试伪装为仅 #288 可独立完成的验证。

所有动作通过 `CrossEntry.start/resume`，确认和双因子使用真实服务；真实银行提交后丢失响应。
冻结用例同时覆盖 #289 的 `composition(response_loss=True)` 配置开关及同一银行故障直接设定。
订单/付款在对应动作前使用同一个银行单次故障，以检查相邻恢复路径；没有替身 ports 或假银行。
模型仅是运行构建替身、没有真实调用；临时数据库独立，不用共享演示数据。

每个用例：真实未知 → 取消 → 从持久检查点重建 entry → 空响应刷新菜单 → 使用新菜单回查。
核对停止原因保留、无新确认卡、原 operation_id 可查、动作集合不增加、订单数量不增加；
再次恢复后银行事实不变。

| 丢响应动作 | 核实收尾后的状态 | 消费（分） | 释放（分） | 剩余冻结 | 订单数 |
|---|---|---:|---:|---:|---:|
| 冻结（#289 配置开关） | cancelled | 0 | 50000 | 0 | 0 |
| 冻结（银行同一故障） | cancelled | 0 | 50000 | 0 | 0 |
| 首笔下单 | cancelled；已有未付款订单保留 | 0 | 50000 | 0 | 1 |
| 首笔付款 | partially_succeeded | 19900 | 30100 | 0 | 1 |

金额以银行 get_freeze/持久事实核对，没有通过预算减法补齐事实。订单失败/取消不冒充撤单退款。

## 运行与审查记录

- 三条直接银行故障路径 + #289 原生日装配回归：**8 passed in 53.68s**。
- 四条最终探针与组合模块回归：待回填。
- 子代理审查与独立复验：待回填。
- 原有 PR 的 CI 计费阻塞记录不因本轮测试变绿；本轮未做真实模型、HTTP/页面 E2E、真人安全或 PM 验收。

可复跑命令：在上述组合 worktree 根目录设置 `PYTHONPATH=<该worktree>/backend`，用项目已有
backend/.venv 的 Python 执行 `-m pytest <本探针绝对路径> -q`。
探针在普通 backend 测试收集范围外，必须明确组合版本；复核完临时 worktree 可归档并通过本对话附件恢复。
