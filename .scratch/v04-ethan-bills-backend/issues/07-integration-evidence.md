# 07：账单真实链路与前端协作证据

Ticket ID: v04-ethan-bills-backend/07
Type: 评测
Owner: 周恩宇（业务评测证据）
Directory: evals/bills/
Status: in_progress
Package: [v04-bills/01](../../v04-bills/packages/01-bills-backend.md)
Spec: [本人规格](../spec.md)
Core scenarios: [BF01—BF07](../../v04-bills/spec.md)
Blocked by: 本阶段真实 L03 报告与两层导出 HTTP 评测已通过；默认工厂仍只注册 L01、生产 L02/L03 准入待所属工作线完成；当前缺合法模型配置，React 页面及专业安全分别验收。其余 HTTP 分支是待补评测，不误记为接口缺失。
Verification: 自然表达、聊天/卡片/结果一致、修改/恢复、两层导出；HTTP、真实模型、页面分别记录；证据交Erwin的v04-bills/02汇总。

## 验收

本票只做评测与证据；前端代码与公共缺陷回对应负责人。不改版本为accepted，不替代联合/专业安全审查。

## Comments

- 2026-10-19：对已就绪 HTTP 报告/导出链路实施并实跑，代码范围仍为 `evals/bills/`，使用注入的评测 runtime；规划器和策略明确为测试替身。实际源码、用例及原始报告见下列实证。HTTP 接缝测试、真实模型、浏览器页面与生产安全准入分别记录。

- 真实模型可行性已单独核查：当前环境未配置 `BANK_LOCAL_CONFIG`；`backend/app/agent_platform/local_demo.py` 的 `create_local_app()` 在缺此配置时抛出 `BANK_LOCAL_CONFIG_REQUIRED`。仅检查配置是否存在，未读取或展示密钥，当前没有可直接运行的合法模型配置。该文件的正式 `build_runtime()` 仍只注册 L01；生产 L02/L03 规划和权限准入尚需所属工作线装配。上述具体缺口不阻止本票使用明确评测 runtime 验证现有 HTTP API。

### 2026-10-19：受测组合、范围与来源校验修复

- 使用已发布验证组合 [99e96737792f375387ca3eb532ff2be0478af33e](https://github.com/DrErwin/hackerthon-bank-agent/commit/99e96737792f375387ca3eb532ff2be0478af33e)，与本地组合 ee470d5 等树；它包含新主线 cd7c91ad 与 L02、L03、/09、/10，尚不代表生产批准或这些票已合入 main。固定受测后端树为 `b5f9f3aa0431cc45861fe83b2c307a4442710fb3`，本票增量仅 7 个 `evals/bills/` 文件。
- 预检真实 HTTP **7 passed in 4.49s**。首个发布源码 `7b06c215ed889b584b0f1bca70654f97dd8017a6` 的正式 runner 在测试前发现必需清单误写不存在的 `security/executor.py`，当场拒绝且未生成原始报告；这不是正式 7 场景通过证据。随后仅把必需文件改为真实 `security/__init__.py`、必需导入改为 `app.security`；实际 `DeterministicExecutor` 定义在 `gate.py`，HTTP 测试主体未改。
- 修正本地源 `cc5a19c8314c8e3cc1e3d9685036d3ea24ea4f2b` 与最终正式受测源码 [5f22c63605ecb83f624f5690f0a76eddff70d185](https://github.com/DrErwin/hackerthon-bank-agent/commit/5f22c63605ecb83f624f5690f0a76eddff70d185) 等树 `fd1481e19ac27b9703c74073fbd9ee67be879653`。独立 Standards 补做前后 125 份 Git 源码和 60 个真实导入模块的正向核对；Spec / Standards 最终均无未解决发现，未把静态阅读代替 runner 可运行性证明。

### 2026-10-19 17:02：七场景正式 HTTP 证据

实际命令 `python evals/bills/run_http_evidence.py --revision 5f22c63605ecb83f624f5690f0a76eddff70d185`。运行时间 `2026-10-19T09:01:53.927591+00:00`—`2026-10-19T09:02:00.176938+00:00`，pytest **7 passed in 5.28s**；7 collected / 0 failed / 0 skipped / 0 errors / 0 collection errors，共 **87 个实际 HTTP 请求**。请求数不当作场景数，符合预期的拒绝可以通过其业务断言。

| 场景 | 实际经过的关键路径 | 结果认定 |
|---|---|---|
| BILL-HTTP-01 | 消息 → 真实 L03 → 银行 → 自动报告捕获 → F21；聊天 report_ids 和播报核对 | 报告 ID/内容一致，18 条真实流水独立复算，零验证挑战 |
| BILL-HTTP-02 | 普通 card 的 F22 / F23 / F24 | 直接 ready，无敏感任务或挑战，HTML 不含逐笔 ID，no-store |
| BILL-HTTP-03 | details 验证前拒绝 → 银行真实验证码 → 同一 bills 导出任务 → CSV | 验证前无明细读数；验证后按报告范围重新读 B08，CSV 逐字段对照实际银行 |
| BILL-HTTP-04 | 同一挑战连续三个明确错误验证码 | 银行逐次拒绝，最终 VERIFICATION_REJECTED，未读明细/下载 |
| BILL-HTTP-05 | 验证时钟推进至银行提供的 code_expires_at | F17 为 409 TASK_TERMINATED；导出/任务为 VERIFICATION_EXPIRED，下载拒绝，两种状态分开记录 |
| BILL-HTTP-06 | 另一普通用户 U2 请求 U1 报告、导出、演示验证码 | 相应 F21/F22/F23/F24/F19 返回 404，无新增银行读取 |
| BILL-HTTP-07 | U1/S1 验证明细成功后，以新 S2 请求同一资源 | 本人报告仍可读，旧敏感文件为 409 SESSION_RECONFIRMATION_REQUIRED |

- 原始报告 `evals/bills/evidence/2026-10-19/20261019T090200185196Z-python3.12.14-http-l03-exports-5f22c63605ec.json.gz`，解压 SHA256 **`25c4a1a45664e70f05e36ce44872c5f667164b6fc5f3a0f208beadc8e987e823`**；压缩 26606 字节、原始 209864 字节，run_id `a2b8c62d-0c5c-4db5-8852-1f456108b681`。模式 `git_object_verified_full_backend_and_eval_sources`，根执行者独立逐 Git 核验 125 份源码、60 个实际 app 导入、7 个唯一样本及 87 个请求。
- 最终归档 [a3ae818ceeed3816d0186a221e71df98abd91a4e](https://github.com/DrErwin/hackerthon-bank-agent/commit/a3ae818ceeed3816d0186a221e71df98abd91a4e) 已推送到 `test/bills/report-http-evidence-07`，树 `7d3ff1269b78022ec651d091a82ddfa9a6394a32`，父提交就是实际受测源码 5f22c636。归档只新增本轮原始报告并更新 README/运行索引，未改受测代码；未另开第三个 PR。
- 独立 Spec 再实跑 03/05/06/07 四场景：**4 passed, 3 deselected in 3.55s**，并核对原始摘要、7 样本/87 请求/125 来源/60 导入、7 份资金不变和 4 条剩余依赖；最终无未解决阻断项。这是对既有七场景的复核，不增加独立覆盖数量。
- 每例真实 `create_app` / FastAPI TestClient、TransferRuntime/Harness、scoped SQLite、既有 `_bills_reads_factory`、SecurityGate/执行器、BankGateway 和种子银行贯通。报告来自注册的实际 `BillsEntry/BillsReportService`，经 ApiService 自动落库，没有手动植入报告或替代银行结果。网关观察器仅转发真实响应并记录范围与数量。
- 每例所有非 `bank_verification*` 银行表摘要保持不变，资金提交次数为 0；敏感导出会合法新增验证挑战/提交/结果记录，因此不声称银行全表不变。验证码原文、其响应摘要、请求体、Cookie 签名和 CSV 全文不进入原始报告；失败归档也只保留源码位置。
- 规划器固定 L03、U1/D1 的声明 allowlist 和 LOW 风险输入属于明确测试替身；银行账本时钟与验证时钟分别说明，到期值由银行返回，未复制有效期规则。进程内 HTTP 不等于部署 TCP/TLS、真实模型、浏览器或生产安全批准。报告 `phase_result=Passed`、`overall_status=partial`、`full_ticket_acceptance=false` 同时保留。
- F21 资源、自动报告落库和 F22—F24 两层导出已经实际贯通，不再统称外部接口缺失。L01/L02 HTTP 全流程、L03 F10 澄清/恢复、跨轮次/会话到期、导出重发/取消/重试、攻击性 HTML/CSV、SSE 重连等属于仍需补测的具体分支；页面、合法真实模型配置、生产准入与专业安全结论按各工作线继续验收。本票保持 `in_progress`。
