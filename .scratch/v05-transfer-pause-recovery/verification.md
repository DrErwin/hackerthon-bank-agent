# 转账风险覆盖暂停：固定源与验证

执行 `/root/transfer_pause_recovery` AI 子代理，2026-10-29。代码只在transfer目录，未操作根的当前银行、任务或浏览器；旧前端工作树干净且无依赖进程后复用为本票分支。基线 `ed25ec08197ab1a6a95474f582c3519e8a1ef909`。

## 最终固定检查

受测源 `09134a2cc288a73c84cd478e2351c4b538f8a803`，backend树 `d6bd13c9aeb3a9fc0431920462ed3b02dad4132f`。一次必要组合完整结束：**108 passed / 0 failed / 0 skipped，exit 0，150.24s**；JUnit自身time为150.029s。

命令在本工作树backend目录执行，使用D盘既有venv Python，PYTHONPATH为本工作树backend和根，PYTHONUTF8=1，并移除子进程BANK_LOCAL_CONFIG与BANK_PENSION_DEMO_PROFILE：

```text
python -m pytest -q app/modules/transfer/ app/agent_platform/test_transfer_runtime.py app/api/test_conversation_dispatch.py --basetemp=C:\Users\57652\.codex\worktrees\v05-frontend-acceptance\pytest-transfer-pause-final-20261029 --junitxml=../.scratch/v05-transfer-pause-recovery/final.xml
```

[原JUnit](final.xml.gz)，SHA256 `091cced60380d9f0162d1d24ce195730657596fb6f87f714ffdcf8ccbb8fd21b`；108唯一节点分布为既有安排冲突2、手工收款检查点9、本票真实HTTP2、本票Workflow20、原Workflow49、平台真实转账16、API聊天续办10。与原中间批大量重叠，只报这一108，不叠加成更大的通过数。[逐文件计数与各附件哈希](verification.json)。仓库Markdown链接、transfer语法编译、差异空白检查均exit0。

## 原红及中间检查保留

| 批次 | 固定来源 | 实际结果 | 原附件 |
|---|---|---|---|
| 最小原红 | 0fe7e939c424e621568078b42f41aff8acc47992 | 2 failed / 5 passed，2.54s | [red.xml](red.xml.gz)，两红均为needs_attention/无动作而非可修改等待 |
| 旧END兼容原红 | dab0a75f01a6b4e80e2341bd0b9b224f965772a7 | 4 failed / 11 passed，1.41s | [legacy-red.xml](legacy-red.xml.gz)，新增同run与新run的原任务恢复两红 |
| 首次修后开发态 | 未固定commit，尚未加入最终绑定和新会话用例 | 15 passed，1.16s | [first-green.xml](first-green.xml.gz)，不能外推到最终源 |
| HTTP开发态 | 未固定commit，最终相位绑定/新会话用例随后扩充 | 20 passed，17.49s | [http-green.xml](http-green.xml.gz)，独立保留，不与108相加 |

## 行为与限制

新路径只适用于独立普通转账在明确提交前的检查；精确ADMISSION/PAUSE/DEPENDENCY_UNAVAILABLE/单一risk-signal-coverage-required及当前operation/revision/parameters绑定都必须吻合。原样重核对仍暂停，修改回有合法事实的参数重新前检、换操作并要求新确认；公共HTTP证明旧确认拒绝、新动作继续要求验证码与模拟人脸，取消后原恢复入口不能复活任务，银行流水仍零。

旧END兼容先核当前归属，再沿准确parent_config。仅可穿过其他状态与owner/session/parent都不变的run_id更新；真正loop的准确前驱必须是同一动作和资料的security节点。缺链、资金资料变化、执行相位、Cross子任务或当前检查返回ALLOW/其他确认/错误均不据此提交。模块不把operation为空当作未执行证据。兼容只发生在原resume入口，GET不迁移；历史检查点仍保留。

真实测试层包含Workflow、Harness、安全门、ASGI TestClient HTTP及隔离MockBank。风险决策与规划器为明示替身，HTTP夹具用600元缺事实这一替身谓词触发同类暂停，不改生产演示配置，不冒称实际A5页面已过。根的实际旧A5任务及截图回归、非作者两轴、精确head CI、合入和真人接受均由根另核。未重跑整套后端或真实模型，没有向共享银行写入。

原XML不改任何换行或失败栈，逐字gzip后保存；原件保留于本工作树所属独立目录 `C:\Users\57652\.codex\worktrees\v05-frontend-acceptance\pytest-transfer-pause-raw-20261029`，解压哈希与上述相同。压缩附件哈希另见verification.json。
