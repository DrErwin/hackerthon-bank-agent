# 冻结未知后取消：回查重新进入下单的跨目录缺陷

Status: blocked — 交中控拆业务依赖，本线不改 `modules/cross`。

发现：2026-10-25，[v05-cross-platform/12：生日一次响应丢失装配](../issues/12-birthday-response-loss-assembly.md) 的独立 Spec 子代理实测。基线 `e9517b8`，平台代码提交 `cfbb398`；cross 文件无改动。优先级建议 P1，阻塞 XL-B06 未知后停止的联合验收。

原要求：[业务票 03](../../v05-cross-business/issues/03-birthday-orchestration.md)：“取消/安全终止停止新购，仅按限定授权处理未消费冻结。”（及[平台原票 09](../issues/09-birthday-runtime-wiring.md)的停止后只收尾要求）。

## 最小复现与实际证据

使用本 worktree 的临时数据库及真实生日 entry、安全门/确认、双因子和银行。模型只用于构建替身，未真实调用；不使用共享演示数据，无 HTTP/页面 E2E。

1. `composition(temp_path, response_loss=True)`；走到冻结确认，批准并完成双因子；`entry.resume(who, {'choice':'resume'})`。
2. 返回 WAITING_INPUT、“冻结结果还待核实”，银行已冻结 50000 分。
3. `entry.resume(who, {'cancel':True})` 返回 RUNNING；此时没有释放，因原操作仍待核实，这是正确的保守等待。
4. `entry.resume(who, {})` 刷新未知菜单；使用**新菜单**的“核实原操作”选项继续（取消前的旧选项失效，不复用）。
5. 实际返回 WAITING_APPROVAL，确认记录 `action_name='bank.create_order'`；银行 `released_total_fen=0`。预期应核实原冻结后只做限定释放，不再提出下单。

## 原因与提供方

- [birthday.py](../../../backend/app/modules/cross/birthday.py) L751–761：未知时取消保存停止原因与 holding，等待核实。
- 同文件 L614–639：`_requery` 核实冻结后直接 `_run_next_order`。
- 同文件 L532–552：`_run_next_order` 未检查停止原因，重新提出订单确认。

提供目录：`backend/app/modules/cross/`，由中控在 business05 完成后顺序安排独立业务票，避免同目录并行修改。最小修复应让未知回查核实后尊重已记录的停止状态、仅进入已有限定收尾流程；还需核对未知订单/付款的停止恢复同类路径并回归“不复活购买”。不新增安全放行政策，不在平台隐藏菜单或把真实未知改成成功。

本票平台装配与原 claim 核实已经通过；这不表示 XL-B06 联合验收通过。新故障入口暴露了旧业务缺陷，不能因它会弹出真实确认就放宽完成声明。未真实提交新订单，未替中控创建/领取业务票或代签验收。
