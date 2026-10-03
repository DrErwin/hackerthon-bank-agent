# v03-transfer-evals/03 实现与实跑证据

Date: 2026-10-04（报告UTC为2026-10-03）
Branch: codex/transfer-eval-suite
Backend/frontend baseline: baca81233e725ee1d1d47fa8020a8acb5ff4221d（前置PR #48/#50已合入）
Status: 自动化实现可审查，业务硬断言仍失败；不是04、原12或v0.3验收通过

## 交付与执行层

八字段矩阵153样本由catalog读取，不删失败样本；plans提供明确输入和前置，scenarios逐组执行真实流程及断言。离线固定proposal，真实GLM用既有DeepAgentPlanner和GLM-5.3 Coding Plan，均连接真实Harness、安全门、网关、隔离MockBankService。资金调用发生前核对该operation对应的执行ALLOW及实际确认/验证授权快照，最终查银行原操作及真实outflow。

F36专用号码不进入模型；HTTP覆盖确认/验证码/模拟人脸/恢复/跨用户权限。变更金额、付款账户或收款人通过既有平台continue_task字段入口，明确不声称React支持这些修改表单。受控风险事实和指定故障是替身，银行余额/限额/账户状态规则由银行判断；历史额度以前期真实outflow装载验证。验证码、私密号码、日志及检查点逐样本扫描，报告再次脱敏。

TF-OBS-03—07是真实构建React、临时TCP HTTP及Chromium；截图、DOM、HTTP请求和构建哈希留存。两项平台回归引用独立运行当前空白HTTP入口与现有非法模型金额校验测试，不复制银行逻辑。

## 实际结果

| 运行 | 转账结果（153分母保持） | 其他事实 | 证据 |
|---|---|---|---|
| 最初离线开发全量 | 118 Passed / 25 Failed / 4 Error / 6 Blocked | 包含评测接缝错误，之后修复；保留首次失败，不当作产品最终结论 | [报告](evidence/2026-10-04/first-offline.md) |
| 首次GLM中断前缀 | 13/153，11 Passed / 2 Failed | 初始专用录入话术未形成任务；之后采用矩阵的明确缺对象转账输入，保留旧结果 | [报告](evidence/2026-10-04/first-live-prefix.md) |
| 首次GLM完整运行 | 130 Passed / 20 Failed / 3 Blocked | 标准21/21；无Error；此时尚未补齐审查漏检，不替代后续结果 | [报告](evidence/2026-10-04/first-live-full.md) |
| 离线pytest完整复跑 | **136 Passed / 16 Failed / 1 Blocked** | pytest总计138 passed、16 failed、1 skipped，另两项为目录完整性及平台回归；标准21/21、缺项追问9/9，5个React通过 | [报告](evidence/2026-10-04/offline-full.md) |
| GLM完整复跑 | **126 Passed / 23 Failed / 4 Blocked** | 标准21/21；缺项追问6/9；5个React通过、平台2/2；无Error，命令退出1 | [报告](evidence/2026-10-04/live-full.md) |
| 最后两项覆盖修正后定向离线 | TF-QRY-03 / TF-RCV-22均Passed | 自动回查期间请求HTTP摘要并计入原截止；真实银行验证完成/绑定中断后保持原operation | [报告](evidence/2026-10-04/offline-followup.md) |
| 同两项定向真实GLM | 两项均Passed | 实际模型规划，不回退；只补充这两项，不重新计算全量结果 | [报告](evidence/2026-10-04/live-followup.md) |

全量复跑评测器指纹为`90d434b9147897a4cbdcb75817f27195aa43a61f3f3605ca40cb675b0020abb1`；最后两项覆盖修正指纹为`94321c6ef99d`开头，完整值在manifest及结构化报告。全量结果与修正后定向结果分别保留，不声称全量已经在最后修正源码重新运行。旧报告没有启动指纹的明确为历史开发记录；它们的开始时间是当时保存时刻，不能用于精确总耗时。

现有后端+模拟银行回归 **287 passed**（150.78秒）；前端构建通过；评测器compileall、文档链接和差异空白核对通过。当前CI不执行本套件，不能用CI绿替代上述失败结果。完整pytest本机309.24秒，原票“秒级全绿”未达到，实际服务测试与失败状态不能伪装为已达标。

发现的资金红线断言违规数0，但全体红线结论为**Unverified**：Ringo攻击证据缺失，专业安全NotRun，秘密留存断言也有实际失败。零次观察不等于安全验收通过。标准100%仅是冻结21合法成功任务的指标；不放宽强制规则或缺项追问100%要求。问题与归属见[问题记录](gaps.md)。

## 可读取的原始证据

每个报告同目录的`.json.gz`是运行时完整report.json的无损压缩，含每条真实输入/proposal、步骤、HTTP响应、确认/任务/银行状态、提交/账本、失败断言及模型异常类型。[manifest.json](evidence/2026-10-04/manifest.json)列出原JSON SHA256、源码指纹与分母。API Key已比对确认未出现在任一导出报告，动态模拟码再次脱敏；未导出原始数据库。

```powershell
python -c "import gzip,pathlib; p=pathlib.Path('evals/transfer/evidence/2026-10-04/live-full.json.gz'); pathlib.Path('.mnemon/live-full-report.json').write_bytes(gzip.decompress(p.read_bytes()))"
```

截图位于[离线OBS03](evidence/2026-10-04/offline-full-browser/TF-OBS-03.png)、[离线OBS04](evidence/2026-10-04/offline-full-browser/TF-OBS-04.png)、[离线OBS05](evidence/2026-10-04/offline-full-browser/TF-OBS-05.png)、[离线OBS06](evidence/2026-10-04/offline-full-browser/TF-OBS-06.png)、[离线OBS07](evidence/2026-10-04/offline-full-browser/TF-OBS-07.png)；GLM对应截图同级`live-full-browser/`。JSON保存原运行绝对截图路径，仓库镜像名称对应样本ID；图片SHA256可复核。

## 双轴AI审查

code-review Skill分别启动Standards与Spec独立审查。首轮发现报告指纹/平台退出码/成功误报红线遗漏及恢复操作号、跨任务验证、回查过期、摘要截止漏检；已修复并按实际结果复跑。Standards复审无新阻塞；Spec最后复审6项覆盖缺口全部修复，无新阻塞。

这两项是**AI审查**，不是Ringo本人审批、Erwin业务签署或人类合并批准。03代码仅在evals/transfer；未启动04，未合并本PR，未更新版本为完成。
