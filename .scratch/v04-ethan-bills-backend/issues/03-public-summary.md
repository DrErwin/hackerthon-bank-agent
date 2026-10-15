# 03：L01公开统计/明细与原任务接入

Ticket ID: v04-ethan-bills-backend/03
Type: 开发
Owner: 周恩宇
Directory: backend/app/modules/bills/
Status: in_progress（L01 模块级代码已提交 #131 / CI 通过；待 Erwin Review/合并/平台真装配）
Package: [v04-bills/01](../../v04-bills/packages/01-bills-backend.md)
Spec: [本人规格](../spec.md)
Core scenarios: [BF01/BF05/BF06](../../v04-bills/spec.md)
Blocked by: 当前无缺失的 B08 / 公共 L01 模型（Issue #91 已关闭；PR #92 已合入）；正式端到端依赖 #131 代码 Review/合入与平台 Issue #123 的真实模块装配、安全策略复核
Verification: 注册L01；本人登录读取、跨用户拒绝、全部账户完整取数、自然语言澄清/修改/原任务恢复；HTTP/模型证据与纯算术分开。

## 验收

- 引用app.contracts公共模型，统一安全执行入口调用B08；无私有银行读取。
- 不自行猜账户/月份，失败不报0；summary/details输出按§5.3。
- 真实接口形态可调用且测试后向frontend-complete/01发出接入信号；仅文档定义不算信号。

## 实际推进与证据（2026-10-15）

- [PR #131](https://github.com/DrErwin/hackerthon-bank-agent/pull/131)：公开 `bills.summarize`、真实 B01/B08 受控读取、同任务澄清/恢复、真实 Harness+SQLite+Mock Bank 集成测试；目前为 **Ready for Review，未合并**。
- [GitHub Actions #38665711607](https://github.com/DrErwin/hackerthon-bank-agent/actions/runs/38665711607)：后端 **591 passed**、模拟银行 **14 passed**，仅表明现有仓库自动检查成功；真实 GLM、HTTP、React 和专业安全审查仍未验收。
- [Issue #123](https://github.com/DrErwin/hackerthon-bank-agent/issues/123)：已向 Erwin 回填 L01 的 10-16 checkpoint 进度；真实模块替换契约形状桩属于平台工作线，不能在本票越界替他合并。
- L01 当前只注册 `bills.summarize`；L02/L03 尚未对外可用，不因局部模块 CI 通过而关闭 BF01—BF07。
