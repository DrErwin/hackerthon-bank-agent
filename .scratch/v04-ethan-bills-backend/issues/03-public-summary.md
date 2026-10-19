# 03：L01公开统计/明细与原任务接入

Ticket ID: v04-ethan-bills-backend/03
Type: 开发
Owner: 周恩宇
Directory: backend/app/modules/bills/
Status: in_progress（PR #131 批准的 L01 模块切片已合入；其余范围与联合验收逐路径记录）
Package: [v04-bills/01](../../v04-bills/packages/01-bills-backend.md)
Spec: [本人规格](../spec.md)
Core scenarios: [BF01/BF05/BF06](../../v04-bills/spec.md)
Blocked by: B08 / 公共 L01 模型及 PR #131 合入依赖已解除；正式端到端和其余范围按平台 Issue #123、本人 06/07 及专业安全的实际证据分别验收，不再把 #131 未合入列为阻断。
Verification: 注册L01；本人登录读取、跨用户拒绝、全部账户完整取数、自然语言澄清/修改/原任务恢复；HTTP/模型证据与纯算术分开。

## 验收

- 引用app.contracts公共模型，统一安全执行入口调用B08；无私有银行读取。
- 不自行猜账户/月份，失败不报0；summary/details输出按§5.3。
- 真实接口形态可调用且测试后向frontend-complete/01发出接入信号；仅文档定义不算信号。

## 实际推进与证据（2026-10-15，合入前历史）

- [PR #131](https://github.com/DrErwin/hackerthon-bank-agent/pull/131)：公开 `bills.summarize`、真实 B01/B08 受控读取、同任务澄清/恢复、真实 Harness+SQLite+Mock Bank 集成测试；目前为 **Ready for Review，未合并**。
- [GitHub Actions #38665711607](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/38665711607)：后端 **591 passed**、模拟银行 **14 passed**，仅表明现有仓库自动检查成功；真实 GLM、HTTP、React 和专业安全审查仍未验收。
- [Issue #123](https://github.com/DrErwin/hackerthon-bank-agent/issues/123)：已向 Erwin 回填 L01 的 10-16 checkpoint 进度；真实模块替换契约形状桩属于平台工作线，不能在本票越界替他合并。
- L01 当前只注册 `bills.summarize`；L02/L03 尚未对外可用，不因局部模块 CI 通过而关闭 BF01—BF07。

## Comments

### 2026-10-19：核对批准切片已合入

- 根执行者核对 GitHub：[PR #131](https://github.com/DrErwin/hackerthon-bank-agent/pull/131) 已于 **2026-10-15T17:53:58Z** 正式合入，合并提交 [85a119deb3fca629ba7661d01e775babef722623](https://github.com/DrErwin/hackerthon-bank-agent/commit/85a119deb3fca629ba7661d01e775babef722623)。上方 Ready for Review / 未合并是合入前记录，当前不再保留该阻断。
- 已合入范围是批准的 `bills.summarize`、受控 B01/B08、原任务澄清/恢复及相应模块/接缝测试切片。本轮 [06](06-full-business-eval.md) 先在新主线真实注册 L01 路径执行 14 个公共场景，随后补三项就绪缺口并完整复跑新版 17 场景，证据另行归档，不累计成 31，也不以既有 591 项 CI 代替新运行。
- 自定义/复杂范围、更多自然语言修改、各细分功能和错误覆盖仍按现行代码与对应评测逐项推进；本票保持 in_progress，不将批准切片合入扩写为全部高级范围、真实模型/页面或专业安全验收通过。
- [08](08-l01-rework-consistency.md) 的 PR #140 历史返修已 resolved；其中合前 P2 为 PM 授权代行修复，原归属与代行记录保留，不算作本轮 Ethan 新做的修改。
