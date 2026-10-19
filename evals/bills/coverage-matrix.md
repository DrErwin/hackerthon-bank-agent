# v0.4 账单需求覆盖与缺口

这是设计索引，不是整条业务通过报告。下表全部使用完整 BILL 编号，原核心用例保留编号。ARITH 只证明相应算术子断言；没有对应自动化的业务仍为 NotRun。逐样本结果和确切版本见 [运行台账](run-log.md)。

| 功能/规则及依据 | 正常 | 反例 | 边界 | 信息/修改 | 失败/恢复 | 风险交叉 | 缺口与依赖 | 当前算术样本/状态 |
|---|---|---|---|---|---|---|---|---|
| 七类/性质/方向；PRD SOP-1、M05 | BILL-001 | BILL-STAT-02/03/04 | BILL-STAT-07 | BILL-STAT-19 | BILL-STAT-15/22 | BILL-SEC-09 | B08/公共模型 #91 | 算术子断言 Passed：ARITH-01, ARITH-02, ARITH-05, ARITH-07, ARITH-08, ARITH-18；业务 NotRun |
| 退款/净消费；M11、§5.9 | BILL-004 | BILL-STAT-06 | BILL-STAT-07 | BILL-STAT-19 | BILL-STAT-22 | BILL-STAT-05 跨月 | 完整退款关联fixture待补 | 算术子断言 Passed：ARITH-03, ARITH-04, ARITH-05, ARITH-07, ARITH-10, ARITH-25；业务 NotRun |
| 环比/同比；§5.3 | BILL-005、BILL-STAT-09 | BILL-STAT-10 | BILL-STAT-08/11 | BILL-STAT-18 | BILL-STAT-10 | BILL-STAT-15 | 具体环比黄金数据待补 | 算术子断言 Passed：ARITH-18, ARITH-22, ARITH-23；业务 NotRun |
| 自然月/半开范围；§2.2/5.3 | BILL-STAT-12/13 | BILL-STAT-14 | BILL-STAT-20/21 | BILL-STAT-18 | BILL-STAT-15/22 | BILL-STAT-16 多账户 | 24月下限以B08公开实现核对 | 算术子断言 Passed：ARITH-16, ARITH-18, ARITH-19, ARITH-21, ARITH-26；业务 NotRun |
| 明细过滤/渠道/脱敏；M16 | BILL-STAT-17、BILL-018 | BILL-LOC-03 | BILL-LOC-04 | BILL-LOC-01 | BILL-STAT-22 | BILL-SEC-07 | 真实资源/公共权限未提供证据 | 算术子断言 Passed：ARITH-32；业务 NotRun |
| 查询失败与空/零；M05 | BILL-003、BILL-STAT-07 | BILL-006 | BILL-STAT-08 | BILL-FLOW-02 | BILL-STAT-15/22/23 | BILL-FLOW-01 | 不能用算术空批次替代真实失败 | 算术子断言 Passed：ARITH-05, ARITH-06, ARITH-07, ARITH-18, ARITH-23；业务 NotRun |
| 规则1独立OR；PRD规则1 | BILL-R1-01/02、BILL-007 | BILL-R1-03 | BILL-R1-04/05 | BILL-LOC-01 | BILL-R1-06 | BILL-008 亲属排除 | 历史流水加载待实现 | 无本轮自动化；业务 NotRun |
| 规则2陌生账户/商户；PRD规则2 | BILL-009、BILL-R2-02 | BILL-R2-01、BILL-010 | BILL-R2-04 | BILL-LOC-05 | BILL-STAT-15 | BILL-LOC-01 | 无ID/历史不足需独立实跑 | 算术子断言 Passed：ARITH-18；业务 NotRun |
| 规则3夜间两端；PRD规则3 | BILL-011、BILL-R3-03 | BILL-R3-04 | BILL-011、BILL-R3-03/04 | BILL-LOC-04 | BILL-STAT-22 | BILL-R3-05 UTC转北京时间 | 恰好06:00待Erwin明确 | 无本轮自动化；业务 NotRun |
| 规则4周期扣款；§5.9/M13 | BILL-012、BILL-R4-03/04/07 | BILL-013、BILL-R4-01/02/08 | BILL-R4-03/04/05/07 | BILL-LOC-01 | BILL-STAT-15/22 | BILL-R4-06/09 | 完整历史fixture及失败种类仍需补 | 算术子断言 Passed：ARITH-18；业务 NotRun |
| L02定位/选择；M16 | BILL-LOC-02 | BILL-LOC-03/05 | BILL-LOC-04 | BILL-LOC-01、BILL-FLOW-04 | BILL-STAT-22 | BILL-FLOW-04 旧选项 | 公开原任务交互依赖#91及平台 | 无本轮自动化；业务 NotRun |
| L03报告内容/口径；M07/M12 | BILL-014/019、BILL-REP-01 | BILL-REP-10/11 | BILL-REP-02/03/04/05/06/07/08 | BILL-STAT-18 | BILL-021 | BILL-REP-09 分享 | 受控报告/资源未实跑 | 算术子断言 Passed：ARITH-14；业务 NotRun |
| 两层导出；PRD安全、§6 | BILL-015/016 | BILL-SEC-02/06 | BILL-SEC-03 | BILL-SEC-07 | BILL-SEC-02/03 | BILL-SEC-04/10 | 资源服务技术故障每类3条仍待补 | 无本轮自动化；业务 NotRun |
| 权限与注入；PRD安全 | BILL-001/015 本人合法读取 | BILL-017、BILL-SEC-04/06/08 | BILL-SEC-03 | BILL-SEC-07 | BILL-FLOW-01 | BILL-SEC-09/10 | 真实安全入口/检测证据未验 | 算术子断言 Passed：ARITH-01, ARITH-02, ARITH-08；业务 NotRun |
| 原任务恢复/取消；BF05/BF06 | BILL-FLOW-01 | BILL-FLOW-04 | BILL-STAT-22 | BILL-FLOW-03、BILL-STAT-18 | BILL-FLOW-01/02 | BILL-FLOW-04 | 需真实持久化/HTTP/模型/页面 | 无本轮自动化；业务 NotRun |
| 展示比例最终舍入/排序；§6.11 | BILL-STAT-24 | BILL-STAT-24 | BILL-STAT-24 | 不适用：固定展示函数 | 不适用：无I/O | BILL-STAT-06 负净额 | ARITH-27/28/29；公共输出集成未验 | 算术子断言 Passed：ARITH-27, ARITH-28, ARITH-29；业务 NotRun |
| 退款原单与数据完整性；M11/M05 | BILL-STAT-25 | BILL-STAT-25 | BILL-STAT-26 | 不适用：计算层无对话 | BILL-STAT-25 | BILL-STAT-27 重复事实 | 原单获取/授权交给B08及业务接入，不能以局部替代 | 算术子断言 Passed：ARITH-03, ARITH-10, ARITH-17, ARITH-20, ARITH-30, ARITH-31, ARITH-33；业务 NotRun |

以上均须在对应公开能力实际实现后逐例核验，引用同一用例不增加独立覆盖数量；依赖失败、专业安全检测与算术校验不是同一层证据。

## 数量与范围

- STAT：本表 26 条；细化的核心编号另按原ID计数（不是通过数）。
- R1：本表 6 条；细化的核心编号另按原ID计数（不是通过数）。
- R2：本表 3 条；细化的核心编号另按原ID计数（不是通过数）。
- R3：本表 3 条；细化的核心编号另按原ID计数（不是通过数）。
- R4：本表 9 条；细化的核心编号另按原ID计数（不是通过数）。
- LOC：本表 5 条；细化的核心编号另按原ID计数（不是通过数）。
- REP：本表 11 条；细化的核心编号另按原ID计数（不是通过数）。
- SEC：本表 8 条；细化的核心编号另按原ID计数（不是通过数）。
- FLOW：本表 4 条；细化的核心编号另按原ID计数（不是通过数）。

与既有21条按稳定编号去重后，共96条设计记录；增量表4条是原核心例细化，同号只统计一次。L01 统计/明细/查询类、L02 异常与定位类、L03 报告/导出类的规划均超过每功能10条；规则1/2/3/4各至少3条。**这不代表每个错误种类的3条目标已独立验收**：导出服务技术故障、报告资源读写故障等仍需在实际公共接口落地后按错误类型补齐；当前不能标“完整验收集已通过”。

当前阶段：v0.4 账单，不扩 cross（v0.5）、卡片、订阅取消或理财。跨用户、权限与验证码验证必须走真实公共入口；局部算术测试不能代替这些检查。

## BF 路径状态

| 核心场景 | 当前可核对证据 | 未完成部分 |
|---|---|---|
| BF01 | 私有统计计算及虚构数据局部测试 | L01注册/B08真实取数/权限/HTTP/模型 |
| BF02 | 四规则及候选定位覆盖设计 | 业务实现/历史流水fixture补全/实跑 |
| BF03 | 月均与对比算术局部测试 | 受控报告生成与端到端返回 |
| BF04 | 两层导出及权限用例设计 | 真实资源/验证路径与下载测试 |
| BF05 | 范围完整性校验局部测试 | 自然语言澄清/原任务修改 |
| BF06 | 缺批次/错误范围拒绝的局部测试 | 原任务持久化/恢复/真实B08失败 |
| BF07 | 交接依赖已明确 | 前端工作线页面与联合验收 |

## ARITH ↔ BILL 双向索引（33 个样本）

样本正向映射以 [fixture_map.json](fixture_map.json) 为机器输入；下表为人读镜像。原核心文件的“待运行”保留为业务层历史状态。所有本表 Passed 仅指私有算术断言，业务全路径不随之通过。

| 样本/参数化 ID | 对应业务定义 | 局部状态 | 业务层状态 |
|---|---|---|---|
| ARITH-01 | BILL-001 | 私有算术 Passed；见 [run-log](run-log.md) | NotRun |
| ARITH-02 | BILL-001 | 私有算术 Passed；见 [run-log](run-log.md) | NotRun |
| ARITH-03 | BILL-004, BILL-STAT-25 | 私有算术 Passed；见 [run-log](run-log.md) | NotRun |
| ARITH-04 | BILL-STAT-06 | 私有算术 Passed；见 [run-log](run-log.md) | NotRun |
| ARITH-05 | BILL-STAT-07 | 私有算术 Passed；见 [run-log](run-log.md) | NotRun |
| ARITH-06 | BILL-003, BILL-REP-04 | 私有算术 Passed；见 [run-log](run-log.md) | NotRun |
| ARITH-07 | BILL-STAT-07 | 私有算术 Passed；见 [run-log](run-log.md) | NotRun |
| ARITH-08 | BILL-001 | 私有算术 Passed；见 [run-log](run-log.md) | NotRun |
| ARITH-09 | BILL-STAT-03 | 私有算术 Passed；见 [run-log](run-log.md) | NotRun |
| ARITH-10 | BILL-STAT-05, BILL-STAT-25 | 私有算术 Passed；见 [run-log](run-log.md) | NotRun |
| ARITH-11 | BILL-019 | 私有算术 Passed；见 [run-log](run-log.md) | NotRun |
| ARITH-12 | BILL-REP-08 | 私有算术 Passed；见 [run-log](run-log.md) | NotRun |
| ARITH-13 | BILL-REP-03 | 私有算术 Passed；见 [run-log](run-log.md) | NotRun |
| ARITH-14 | BILL-REP-02 | 私有算术 Passed；见 [run-log](run-log.md) | NotRun |
| ARITH-15 | BILL-REP-07 | 私有算术 Passed；见 [run-log](run-log.md) | NotRun |
| ARITH-16 | BILL-STAT-12 | 私有算术 Passed；见 [run-log](run-log.md) | NotRun |
| ARITH-17 | BILL-STAT-26 | 私有算术 Passed；见 [run-log](run-log.md) | NotRun |
| ARITH-18 | BILL-STAT-15 | 私有算术 Passed；见 [run-log](run-log.md) | NotRun |
| ARITH-19 | BILL-STAT-12 | 私有算术 Passed；见 [run-log](run-log.md) | NotRun |
| ARITH-20 | BILL-STAT-27 | 私有算术 Passed；见 [run-log](run-log.md) | NotRun |
| ARITH-21 | BILL-STAT-16 | 私有算术 Passed；见 [run-log](run-log.md) | NotRun |
| ARITH-22 | BILL-005 | 私有算术 Passed；见 [run-log](run-log.md) | NotRun |
| ARITH-23 | BILL-STAT-08 | 私有算术 Passed；见 [run-log](run-log.md) | NotRun |
| ARITH-24 | BILL-STAT-11 | 私有算术 Passed；见 [run-log](run-log.md) | NotRun |
| ARITH-25 | BILL-STAT-06 | 私有算术 Passed；见 [run-log](run-log.md) | NotRun |
| ARITH-26 | BILL-STAT-16 | 私有算术 Passed；见 [run-log](run-log.md) | NotRun |
| ARITH-27 | BILL-STAT-24 | 私有算术 Passed；见 [run-log](run-log.md) | NotRun |
| ARITH-28 | BILL-STAT-24 | 私有算术 Passed；见 [run-log](run-log.md) | NotRun |
| ARITH-29 | BILL-STAT-24 | 私有算术 Passed；见 [run-log](run-log.md) | NotRun |
| ARITH-30 | BILL-STAT-25 | 私有算术 Passed；见 [run-log](run-log.md) | NotRun |
| ARITH-31 | BILL-STAT-25 | 私有算术 Passed；见 [run-log](run-log.md) | NotRun |
| ARITH-32 | BILL-STAT-17 | 私有算术 Passed；见 [run-log](run-log.md) | NotRun |
| ARITH-33 | BILL-STAT-25 | 私有算术 Passed；见 [run-log](run-log.md) | NotRun |
