# demo-safety-model-data/01：检查并补齐 Demo 安全判断数据

Ticket ID: demo-safety-model-data/01
Package: 本轮用户直接授权的数据检查与补充（无另设交付包）
Spec: [Demo 安全模型候选数据准备](../spec.md)
Owner: AI 按用户授权代行；目录归属 Ringo，非本人审查
Directory: evals/security/
Status: Done — 数据准备与本地检查完成、首批已提交 main（2026-10-22），候选模型未运行
Blocked by: None
Core scenarios: 赛程安全合规四方向，覆盖转账、账单及订阅相关表达；仅检测层样例，不新增业务功能
Verification: 数据结构、编号、去重、分组隔离、标签与场景语义逐项核对；不跑模型或全量业务回归

交付：现有数据质量判断、独立 JSONL 样例及使用说明，README 增加入口。历史用例与成绩保持原样。

## 完成记录（2026-10-21）

- [质量检查与使用说明](../../../evals/security/model-selection/README.md)、[样例数据](../../../evals/security/model-selection/cases.jsonl)已落地，上级 README 已增加入口。
- 56 条、14 场景族：反诈 32，信息套取/越权/注入各 8；risk 28、benign 14、unclear 14；dev 32、check 24，场景族不跨组；3 条多轮输入。
- Python 标准库校验通过：JSON 解析、ID 与完整输入唯一、数量和标签、场景族隔离、原有 SEC/MAT 引用、相对文件链接、保留测试域名、编码与空白。最后数据调整后已复核结构、计数、分组、多轮、链接与空白；git diff --check 通过。
- AI 逐条内容复核；F08-03 增加可信演示验证框前置，避免把未知页面当作正常；F07-02、P01-02 补成多轮。
- 数据 SHA256：`3783826a98180f4f89e49a8ea0ecc8abb87bd1c78efb61567289ab54bb3c0ace`。
- 未运行付费模型、原安全 runner、全量回归或 CI。首批数据与说明已于 2026-10-22 随文档/数据提交通道直接提交 main（纯数据与说明，未跑模型）。样例全部 NOT_RUN，未将数据完成标为模型通过或专业批准。
- 下一步（追踪 [Issue #215](https://github.com/DrErwin/hackerthon-bank-agent/issues/215)）：扩充样例（变形改写、真实求助语气、边界对照、跨轮、账单/订阅表达），再做候选模型比较；PM 确认「Jev」模型身份与额度前不调用付费模型。本票不包含模型接入实现。
