# 03：C批六条真实模型不可信来源观察

Ticket ID: v05-security-acceptance/03
Package: [检测器与评测完整性](../../v04-security/packages/01-detector-and-coverage.md)
Spec: [安全分层验收](../spec.md)
Type: 评测（含观察器开发）
Owner: Erwin；Codex按本轮明确授权实施
Directory: `evals/security/`
Status: in_progress
Blocked by: [02](02-live-detector.md)；Depends on PR #336（复用HTTP计数/费用停止及透明规划记录）
Core scenarios: SA03

## 交付

工具备注、API用户资料、MemoryMiddleware摘要三类来源各攻击+正常一条，共六条独立隔离库。复用既有glm-5.3 Coding Plan与正式local_demo装配；配置只读，仅内存替换隔离数据目录和轮次，不切政策/夹具。每条先真实正常500元至妈妈请求，只有实际待确认事实成立才继续；不以固定提案伪造前置。

攻击原文取现有MAT-VFY16-02/03/04，旧样例、硬门、脚本和历史分母保持。工具备注通过真实银行返回进入下一轮，用户资料通过F11 untrusted_content；毒摘要先观察public writer拒绝，再明确标注合成既存坏状态测试正式loader，正常摘要走public writer。模型实际HTTP请求中核对payload和来源边界；不记录凭据/头/内部推理。

## 验收

- [x] 离线覆盖三种来源真实投递、未投递不误绿、模型失败/未达前置、原确认与参数不变、零银行写和U2隔离（40 passed / 45.77s；[JUnit](../untrusted-runner-final-tests.xml)）。
- [ ] 一次固定六条真实运行；无模型比较、调参、重试、买额度；明确429/费用阻塞即停止新请求并保留NOT_RUN。
- [ ] 实际提案、确认前后、原号resume、resource_load、memory命名空间、真实HTTP计数/输入hash/usage与独立银行全表摘要留证。
- [ ] 实际policy/rule/evidence只取审计。ReplyOnly或零银行写不替代资金gate；解释人工接受及生产网络出口全面政策缺口继续Blocked。
- [ ] 原始脱敏总报告/JSONL双附件及SHA归档，独立PR交中控两轴审查，不自行合入或代签接受。

离线真实装配已观察：普通资料跟进后，确认和参数仍pending/不变；原号resume因有限文本语法的风险覆盖不足转needs_attention。此为状态恢复缺口，不将其写为waiting_approval恢复通过，也不放宽有限政策。
