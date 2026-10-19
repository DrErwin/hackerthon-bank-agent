# 票 07：真实 L03 报告与导出的 HTTP 证据

负责人：周恩宇（Ethan）。实施范围：`evals/bills/`。本阶段增加 7 个报告与导出场景，沿实际 HTTP 接口运行。票 07 整体保持部分完成；源码准备、预检、已发布源码上的正式归档、真实模型和页面验收分别记录。

依据：[票 07](../../.scratch/v04-ethan-bills-backend/issues/07-integration-evidence.md)、[BF01—BF07](../../.scratch/v04-bills/spec.md)、[冻结公共契约 §5.3 / §6.4—6.7](../../docs/contracts/公共契约-2026-09-23.md)、[评测指南](../README.md)。机器映射见 [report-http-cases.json](report-http-cases.json)，自动化见 [test_report_http_eval.py](test_report_http_eval.py)。

## 受测实现和注入边界

受测后端是验证组合 [99e96737792f375387ca3eb532ff2be0478af33e](https://github.com/DrErwin/hackerthon-bank-agent/commit/99e96737792f375387ca3eb532ff2be0478af33e) 的完整源码，后端树为 `b5f9f3aa0431cc45861fe83b2c307a4442710fb3`。组合包括主线 `cd7c91ad` 与已发布的 L02、L03、票 09、防泄漏读取审计改动；该验证对象不表示这些能力已获准进入生产。正式报告引用的是在组合上加入本评测源码后、能够从 GitHub 取得的独立 40 位源码提交，不把本地组合标识当作已发布受测版本。

每例独立创建虚构银行和应用 SQLite 数据库。`create_app(runtime=..., config=...)` 使用真实 TransferRuntime/Harness、持久化 checkpoint 和 API 服务；通过公开的 `register_bills_report` 注册真正的 L03 Entry/Service。使用现行 `local_demo._bills_reads_factory` 的任务范围接线、真实 SecurityGate 和确定性执行器读取银行。`BillReport` 来自 HTTP 消息触发的业务结果，随后由 ApiService 自动捕获；评测没有调用 `capture_report` 人工植入报告，也没有替代报告 Entry。

以下输入是明确的测试替身：Planner 固定选择 `bills.generate_report`；准入只接受 U1/D1 的既有 L01/L03 精确声明及两项私有读取声明；风险输入固定 LOW。它们不等同于 DemoSecurityPolicy 的生产审批。网关观察器只转发真实方法并记录关联与数量，不替换银行返回。银行流水时钟固定为北京时间 2026-10-14 13:00；验证服务使用独立可控时钟，从每例真实运行时间起步。到期场景把该时钟推进至 F16 返回的银行截止时间，银行自己计算过期，评测不改挑战状态、不复制有效期规则。

HTTP 经 FastAPI 中间件、Cookie 身份、业务路由和资源服务，以进程内 TestClient 运行。没有启动部署服务器、网络 TLS、真实模型或浏览器。跨用户样本通过第二个公开注入的 ApiConfig 建立普通 U2 会话；它与 U1 共用实际资源库，实际接口负责拒绝越权。

## 八字段场景表

所有场景先经 F01/F03/F05 创建真实 L03 报告，并独立用真实 B08 复核 9 月两个本人账户的 18 条流水：消费毛额 586400 分、退款 4500 分、消费净额 581900 分。复算直接检查银行公开流水，未调用账单计算器作为期望值。每例记录实际请求及 task/run/session/report/export/challenge 关联，资金提交次数为零，所有非验证银行表的摘要保持不变。

| 编号 | 业务维度 | 映射依据 | 前置环境与数据状态 | 用户指令/输入 | Agent 预期交互 | 预期结果与硬性断言 | 自动化映射 & 状态 |
|---|---|---|---|---|---|---|---|
| BILL-HTTP-01 | 真实报告资源与聊天一致 | BF03；§5.3 L03；F05/F06/F08/F21 | U1/D1 有效会话，真实种子银行、L03 已显式注册 | 2026年9月所有账户账单报告 | 脚本规划选择真实 L03，业务读取银行后直接返回报告 | 原 task 有真实 checkpoint；F21 与任务同 report_id/内容；助手 report_ids 与播报相同；金额按银行独立复算；无验证挑战 | `test_report_http_case[BILL-HTTP-01]`；代码已实现，正式结果见[运行台账](run-log.md) |
| BILL-HTTP-02 | 普通卡片直接导出 | BF04；§6.7 F22/F23/F24 | 已有真实 L03 报告，未进行任何验证 | F22 kind=card | 直接准备普通 HTML 卡片 | ready、task_id=null；F23/F24 可取；HTML 有报告播报，没有逐笔交易 ID；no-store；银行验证挑战数仍为 0 | `test_report_http_case[BILL-HTTP-02]`；代码已实现，正式结果见[运行台账](run-log.md) |
| BILL-HTTP-03 | 明细验证前后权限 | BF04；§6.7；F16/F17/F19 | 同上，创建新的敏感明细导出 | F22 kind=details；通过专用 F19/F17 提交真实演示验证码 | 先等待验证，再沿同一敏感导出任务完成 | 验证前 F24=409，下载路径为空且导出任务未读 B08；成功后任务仍属 bills，F23=ready；按原报告账户/日期重新读 B08；CSV 每个字段与银行事实一致 | `test_report_http_case[BILL-HTTP-03]`；代码已实现，正式结果见[运行台账](run-log.md) |
| BILL-HTTP-04 | 错误验证码 | BF04/BF06；§4.2 与 §6.7 | 已创建同一明细挑战 | 连续 3 次提交与实际正确值不同的验证码，各用独立 submission_id | 真实银行逐次拒绝，最终终止导出任务 | 每次 kind=rejected 且 F24=409；最终任务/export 都失败，export.error=VERIFICATION_REJECTED；未读取导出明细 | `test_report_http_case[BILL-HTTP-04]`；代码已实现，正式结果见[运行台账](run-log.md) |
| BILL-HTTP-05 | 银行验证到期 | BF04/BF06；§6.7；F16/F17/F23/F24 | F16 返回真实 code_expires_at，之前取得的正确验证码尚未提交 | 推进验证时钟至银行截止时间，再提交旧正确码 | 银行自行判定到期，接口拒绝继续 | **F17=409 TASK_TERMINATED**；F23=failed/error=VERIFICATION_EXPIRED；F09 原导出任务 failed；F24=409；未读取导出明细。POST 错误与导出到期状态分开记录 | `test_report_http_case[BILL-HTTP-05]`；代码已实现，正式结果见[运行台账](run-log.md) |
| BILL-HTTP-06 | 跨用户资源归属 | BF04；§6.3 与 §6.7 | U1 已有报告、可用 card 与等待验证的 details；另建普通 U2 会话 | U2 读取 U1 报告/导出/验证码，并请求新导出 | 实际 API 在资源归属层拒绝 | F21、F22、F23、F24、F19 均 404；不新增任何银行调用；不泄漏报告与明细 | `test_report_http_case[BILL-HTTP-06]`；代码已实现，正式结果见[运行台账](run-log.md) |
| BILL-HTTP-07 | 新会话不能复用敏感授权 | BF04/BF06；§6.7 | U1/S1 已完成真实明细验证且成功下载；U1 再建立 S2 | S2 请求同一 report_id 与旧 export_id 下载 | 普通报告仍归本人；敏感文件需当前会话授权 | S2 的 F21=200；旧敏感 F24=409 SESSION_RECONFIRMATION_REQUIRED；不能复用 S1 的已通过验证 | `test_report_http_case[BILL-HTTP-07]`；代码已实现，正式结果见[运行台账](run-log.md) |

“同一敏感导出任务”指 F22 创建的 bills 导出任务，和先前 L03 生成报告的任务分别记录。明细身份验证会合法增加银行验证挑战、提交与结果记录，因此“银行数据未变”只指所有非 `bank_verification*` 表；不会把验证记录变化说成银行全表不变。

## 后续依赖与未覆盖范围

| 路径 | 本阶段状态 | 提供方 | 当前缺少的内容 |
|---|---|---|---|
| 生产 L02/L03 登记与明确准入 | Blocked | Erwin / Ringo | 默认工厂只登记 L01，DemoSecurityPolicy 只包含 L01 公开声明；需要明确接入两项新能力 |
| 真实模型自然语言路由 | Blocked | Ethan / Erwin | 合法模型配置与单独真实模型运行；本阶段 Planner 为测试替身 |
| 前端账单插槽与页面流程 | Blocked | 前端负责人 / Ethan | frontend-complete/01 及页面协作环境；本阶段没有浏览器执行 |
| 专业安全与生产策略验收 | Blocked | Ringo | 本阶段仅证明既有 API、真实银行验证对测试输入的实际行为，不能代替专业审查 |

**已有底座不能误记为缺失：** F21 资源、F22—F24 两层导出、自动报告捕获、验证任务与下载检查均已提供；本阶段证明在显式注册真实 L03 后可以贯通。生产缺口是默认运行时登记、安全声明和联合验收，并非没有这些公共接口。

这 7 条未覆盖 L01/L02 的 HTTP 全流程、L03 的 F10 范围澄清和恢复、跨轮次或登录到期变体、导出重发/取消/失败重试、攻击性 HTML/CSV 输入、SSE 重连及页面交互。它们是尚缺的评测分支，不作为外部依赖借口，不表示这些接口不存在。票 06 的业务完整规模与专业安全清单另计；不把 7 条场景、其中的 HTTP 请求数或历史算术测试相加冒充独立覆盖。

## 运行和准确归档

```bash
python -m pytest -q evals/bills/test_report_http_eval.py
python evals/bills/run_http_evidence.py --revision <已发布的40位源码提交SHA>
```

预检通过后先发布准确受测源码，随后运行正式 runner，再提交报告与台账。runner 核验后端树、所有后端和本目录 Python/JSON/SQL/TOML、真实包初始化器及具名契约/用例文件的 Git blob；执行前后校验，并核对实际 `app.*` 导入路径。完整后端树须为本阶段声明的组合，代码改变后应建立新的受测阶段，不复用旧证据。

报告追加至 `evidence/<北京时间日期>/*-http-l03-exports-<源码SHA前12位>.json.gz`，独占创建、不覆盖。索引登记解压 JSON 的 SHA256、实际源码提交、运行时间和状态；每例保留实际起止时间、HTTP 状态/安全摘要、关联标识、真实银行调用范围/数量和资金不变证明。F19 的验证码原文、其响应摘要、请求体、Cookie 签名及 CSV 全文不写入报告；失败只归档源码位置，避免断言 traceback 复制这些内容。

`phase_result=Passed` 仅表示这 7 条已执行断言符合预期，包括正确拒绝。`overall_status=partial`、未就绪依赖及未覆盖范围始终保留；不关闭票 07、不替代 BF01—BF07 或生产验收。
