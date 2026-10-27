# 02：B批四个真实检测实例的12轮观察

Ticket ID: v05-security-acceptance/02
Package: [v04-security/packages/01-detector-and-coverage：检测器与评测完整性](../../v04-security/packages/01-detector-and-coverage.md)
Spec: [安全分层验收](../spec.md)
Type: 评测（含观察器开发）
Owner: Erwin；Codex 按本轮授权实施
Directory: `evals/security/`
Status: in_progress
Blocked by: [v05-security-acceptance/01](01-classification-96.md)（96批已执行，复用其HTTP计数/费用停止helper；Depends on PR #333）
Core scenarios: SA02

## 交付

在新隔离库按原文运行SEC-T-003/v01+v02、SEC-T-004/v01、SEC-T-005/v01各3轮，真实DeepAgentPlanner与可信输入→实际detector接线。普通/信息不足对照另列，不计入12轮。没有匹配夹具，不填unknown为checked，不为进gate猜测金额或收款人。

实际生成资金裁决时记录真实policy/rule/provenance及原号恢复；若模型ReplyOnly或等待补全而未到资金gate，则明确Blocked/无gate证据，不能冒充BLOCK/PASS。独立银行操作/流水与网关提交次数核对零未授权副作用。旧MAT/live硬门不删除；新显式观察入口的范围单列。

## 验收

- [ ] 离线证明：实际detector分支、ReplyOnly/缺字段无gate、失败/ERROR不误绿、原始输入不补参。
- [ ] 一次固定12轮+单列对照，真实模型/HTTP计数/hash/原始脱敏输出与实际裁决保留；429/明确额度费用阻塞即停，无重试或模型切换。
- [ ] 未观察字段为null+具体Blocked；零副作用检查独立，不从模型回复推成功。
- [ ] 单目录独立PR，后继C另票；不关闭#160或代签接受。

Verification: 先当前观察器离线测试，再固定模型批；报告先仓库外新路径，保留全部12轮与未运行分母，归档双SHA256。
