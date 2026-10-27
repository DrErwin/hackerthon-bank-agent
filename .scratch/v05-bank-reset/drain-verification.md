# B26 网关排空与成功逻辑起点：本地证据

Ticket: [v05-bank-reset/02：整体重置的网关排空与成功时钟读取](issues/02-gateway-drain-and-clock.md)
Date: 2026-10-27
Base: `aac4a5fb36ded6cabc0d24f6730e2fc8ff367118`（已含PR #322）
Branch: `codex/v05-bank-gateway-drain`
Status: 本地实现/回归完成；独立审查、合入及整体API验收待中控

## 实际行为

- `wait_for_inflight(timeout)`用网关自己的Condition与future集合，提交与登记同锁；排队、执行中、调用方已超时的写一直保留，完成回调才移除/唤醒。无API锁、无executor关闭、无取消/重发、无银行规则改写。
- 六类写分别被Event拦在真实银行方法前：调用方已得到CALL_TIMEOUT、原银行操作仍not_found时，网关仍返回False。Event释放后等待True，原号查到真实成功；同网关下一笔仍成功。
- 六笔请求超过四个worker，后两笔尚在队列；前四笔放行后仍False，六笔全部真实完成后才True。异常future结束后不留下幽灵在途。
- `current_demo_logical_at`从保留管理记录读最近成功起点。初始、首次running及首次failed为None；成功/重启读同一起点；后续running/failed与旧成功重放不覆盖；第二次真实成功才更新。

## 验证

新网关测试首轮相对导入写法导致收集错误，更正为既有绝对导入后，改实现前**8 failed**，均为缺`wait_for_inflight`。修复后局部网关+银行重置**19 passed in 3.58s**；后续加强了第二轮running起点检查，以下组合回归包含最终源码。

在隔离worktree的backend目录，以已装依赖解释器执行、PYTHONPATH指向本工作区：

```powershell
$env:PYTHONPATH=(Get-Location).Path
& 'D:/hackerthon-bank-agent/backend/.venv/Scripts/python.exe' -m pytest app/services ../evals/mockbank -q --tb=short --junitxml=../.scratch/v05-bank-reset/drain-results.xml -o junit_family=legacy
```

**158 passed / 0 failed / 0 skipped in 50.05s**，含原149节点与新增网关8、后续起点1。见[JUnit](drain-results.xml)，SHA256 `d8834c1821c936bf2dcf7b14aae1b4ed5be2ffb496277ddc9fb9e6f567e7846c`。链接脚本与`git diff --check`通过。提交前fetch，origin/main仍为上方base。

## 交接边界

API先持久停收，并在mutation_lock内核对active_message_jobs及本公开接口；本方法只证明本实例已提交future结束，不能替代准入屏障或跨进程执行追踪。timeout=0.0可即时判断，False时保留同管理ID继续等待。银行processing检查仍是额外保护，不能视为所有生日写/释放的完整排空。

平台启动时可读银行当前轮次与最近成功逻辑起点；clock为构造时共享callable，应推进同一个可变时钟对象，不能只替换bank.clock。应用/记忆/审核历史/管理确认的整体顺序由API和平台各自票负责。

本票只在全新隔离SQLite测试，未操作共享库，无真实模型、HTTP浏览器或截图调用；未跑后端全量，CI尚无通过结论，未代签真人安全/最终体验接受。安全96分类规划干净保留在另一工作区，真实批次尚未开始。
