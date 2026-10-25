# demo-safety-model-data/01：检查并补齐 Demo 安全判断数据

Ticket ID: demo-safety-model-data/01
Package: 本轮用户直接授权的数据检查与补充（无另设交付包）
Spec: [Demo 安全模型候选数据准备](../spec.md)
Owner: AI 按用户授权代行；目录归属 Ringo，非本人审查
Directory: evals/security/
Status: In review — 首批 56 条已在 main；新增 40 条已提交 [PR #270](https://github.com/DrErwin/hackerthon-bank-agent/pull/270)。2026-10-24 PM 决定取消候选模型比较，只扩充样例（见 #215）
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
- 2026-10-24 扩充已提交 [PR #270](https://github.com/DrErwin/hackerthon-bank-agent/pull/270)：新增 40 条，覆盖变形改写、银发求助、边界对照、跨轮与跨会话、账单及订阅表达。候选模型比较已取消；已有真实模型探针仅作历史参考，不重跑。本票不包含模型接入实现。

## 2026-10-25 接续审查与修复

- 执行者：Erwin 授权的安全评测执行对话，2026-10-25 接续 demo-safety-model-data/01；主工作区未编辑。隔离 worktree `security-evals`，本地分支 `codex/security-model-data-review`，继续更新 PR #270 原 head `test/security/model-selection-expansion`。
- 固定审查基线 `e9517b8`；复用了 PR270 的真实差异并 rebase 最新主线。PR 仅样例与说明；本记录属于本人票据，不改共享项目跟踪或版本状态。
- 独立 Standards 与 Spec 子代理均发现表达族编号隔离掩盖语义近重复：养老返利、投屏索码、外部备注伪授权外发。保留所有输入/编号/标签，按 README 关联机制合组；原 dev52/check44 分组废弃，当前 dev68/check28。没有为保旧计数而拆分近重复，四维度独立盲测缺口明确列出。
- 两项独立审查最终复验：已报告必须项均修复，无剩余必须项。数据内容审查不证明统计独立性、模型能力或真人签核。
- Python 标准库核验：96 行解析、ID/完整输入各96唯一、24族各2 risk/1 benign/1 unclear、48/24/24总标签、68/28分组、各族不跨组；SEC/MAT引用与相对文件链接可定位。与原PR head逐条比较，除 split 外数据完全一致。数据 SHA256 `d5bc3c711d4173cbf0ae8ef6c8fc68f8439d6de7ad59e67a0485a06ae633cd53`。`git diff --check` 通过。
- 同步上级 README 的96条入口及取消候选比较。原创合成沿用原作者声明，审查核验文本和虚构边界，未伪称独立采集或证明无外部相似语句。
- 未调用任何模型、未运行安全runner、未跑业务回归或CI；全部96条 NOT_RUN。#160 未裁定、#271 不在本票修。待中控排队合入；未自行合并或接受。
