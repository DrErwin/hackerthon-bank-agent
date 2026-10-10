# 队员开工：领取交付包与通用 Skill

最后更新：2026-10-11。

所有工作线统一走：**确认身份 → 领取交付包并记录 → 检查 Skill → to-spec → to-tickets → 按票执行 → 验证与进度更新**。开发票使用 `implement`，评测、设计和文档票按其交付物执行。交付包的业务范围和开始条件以[跨团队交付原则](../principles/04-cross-team-delivery.md)及正式项目跟踪为准。

## 1. 队员说“我是某某，接下来做什么”时

AI 必须读取 `AGENTS.md`、[项目跟踪](../01-项目跟踪.md)及对应交付包，核对姓名、当前版本、目录归属和开始条件。多个包可接时列出选择；没有可接的包时说明具体依赖及提供方。

回答必须指出包名、包链接、当前可做的范围、依赖及验收结果，并引导队员确认领取。不能只给一份工作清单就跳过交付包和拆票。说“我是谁 / 下一步做什么”属于咨询；明确说“领取这个包 / 开始这个包”才是接受和推进授权。

已有接受记录时直接从未完成步骤继续，不重复要求认领，也不重复生成已有 spec 和票。包中有多位负责人时，每个人只领取自己被分配的工作线；协助人领取前须明确负责范围。

定位、领取及交接使用[完整交付包与票据标识](issue-tracker.md)。只给本地编号时先确定工作组；多人共享交付包的各工作组分别编号，项目跟踪与对外引用写完整票号、标题及链接。

完成条件：身份、包和本人负责范围明确，队员已明确接受。

## 2. 确认领取后，AI 在同一任务自动记录

交付包顶部保留 `Status`、`Owner`、`Activation`、`Start when` 和共享 `Spec`，新增以下记录：

```text
Accepted by: <实际接受人；多人包逐人列出负责工作线>
Accepted at: <实际接受日期 YYYY-MM-DD；多人逐人记录>
Work spec: <本人详细 spec 的相对链接；尚未建立时写待建立>
```

同时更新 `docs/01-项目跟踪.md`：包链接、领取人及工作线、接受日期、状态、阻塞项；生成 spec 和票后补链接与实际开始日期。本人明确领取已经授权 AI 更新这些过程记录，不再为每个字段询问确认。

- 领取记录与包状态分开：接受时写人和日期，开始写 spec、拆票或执行时进入 `in_progress`；依赖未满足仍为 `blocked`，并写明原因。
- `accepted` 专指交付包通过联合验收，不能用它表示刚刚领取。
- 多人包分别记录工作线状态；只有本包整体验收通过才把包设为 `accepted`。
- 旧包没有接受证据时写“未记录”，不能用 Owner 或 Activation 推算本人接受日期。已有实现和测试证据照常保留。
- 自动记录是 AI 写入仓库文件。记录经提交、推送和合入后其他人才能拉取；飞书仍由人决定同步时间，未同步时明确说明。

过程记录允许修改本人交付包、本人 `.scratch/` 和项目跟踪中对应条目；业务实施仍遵守单目录边界。修改共享跟踪前核对最新 `origin/main`，只更新本人的条目，保留他人记录；提交、PR 和合并遵守[Git 约定](git-workflow.md)与[Review 原则](../principles/03-review-and-merge.md)。

完成条件：交付包与项目跟踪均有真实接受记录，阻塞状态明确。

## 3. 通用 Skill 清单与安装检查

只要求流程通用 Skill，不把前端、业务或行业专用 Skill 设为全员开工门槛。

| Skill 准确名称 | 用途 | 需要时点 |
|---|---|---|
| `to-spec` | 将已确认的交付范围写成详细规格 | 领取后写 spec 前 |
| `to-tickets` | 将 spec 拆成带依赖和验收条件的独立票 | 拆票前 |
| `implement` | 按开发票实现、验证并交付 | 有开发票时 |
| `code-review` | 分别核对仓库规范和原始 spec / 票据 | 代码交付审查时 |

安装来源统一为 [mattpocock/skills](https://github.com/mattpocock/skills)。四项路径分别为 `skills/engineering/<Skill名称>/SKILL.md`。2026-09-30 核对的来源提交为 `d81f3a183412e71a5b1e84ca21bc1a35eea03a60`；安装时以此提交为基线，升级需明确记录新来源提交，不静默替换团队基线。

AI 在领取后检查本机 Skill 清单并读取相应 `SKILL.md`：既检查文件存在，也检查当前会话能否使用。`disable-model-invocation` 的 Skill 需要队员显式调用 `/to-spec`、`/to-tickets`、`/implement`，或在当前工具中显式选择对应 Skill；不能因为文件存在就宣称已自动调用。

缺失时先用本环境的 Skill 安装工具，按上面的固定仓库、路径和提交安装缺少的项，不覆盖已有定制 Skill。以 Codex 的 `skill-installer` 为例：

```text
python <skill-installer目录>/scripts/install-skill-from-github.py --repo mattpocock/skills --ref d81f3a183412e71a5b1e84ca21bc1a35eea03a60 --path skills/engineering/to-spec skills/engineering/to-tickets skills/engineering/implement skills/engineering/code-review
```

命令中只保留本机缺失的路径。没有该安装工具时可按[上游安装说明](https://github.com/mattpocock/skills#installation-30-second-setup)安装所需四项，并核对实际来源提交；无法安装时报告失败原因和受阻步骤。安装后再次检查，新安装项需在下一轮或重开会话后可用时，明确提示队员继续的入口。详细 spec 的 `Further Notes` 记录本机检查日期、结果、Skill 来源提交及待解决项，不把本机绝对路径写成团队通用要求。

仓库已有 [issue tracker 配置](issue-tracker.md)与[领域文档约定](domain.md)，无需每位队员重新运行 `setup-matt-pocock-skills` 或改用 GitHub Issues。`implement` 提到的 `tdd` 只在需要按先测试后实现的方式开发时使用，不是全员必装项。

完成条件：本轮需要的 Skill 可用；缺失能力没有被普通回答冒充为已调用 Skill。

## 4. 固定的 spec、tickets、执行流程

验收顺序统一为：**先明确核心场景与测试覆盖框架 → 拆票并明确本票验证 → 按票实现和验证 → 路径就绪即联调 → 核心检查通过后全面验收**。完整规则见[跨团队交付原则 §3](../principles/04-cross-team-delivery.md#3-标准流程)；单目录业务也沿用这一验收顺序，不额外制造交付包层级。

1. **to-spec**：读取交付包、共享 spec、对应 PRD、架构与冻结公共契约；只澄清影响范围、验收或安全选择的未决问题。已有批准决定直接引用。规格落在 `.scratch/<owner-feature>/spec.md`，引用原包，写清本人目录、交付物、验收与依赖。
2. **to-tickets**：按已经确认的规格拆分；按 Skill 要求让负责人确认粒度与依赖，然后每票一个 `.scratch/<owner-feature>/issues/NN-*.md`。每票按[票据标识规范](issue-tracker.md)写完整 `Ticket ID`、所属 `Package`、`Spec`，并写 `Type`（开发 / 评测 / 设计 / 文档）、`Owner`、归属目录、`Status`、`Blocked by`、交付物及可检查的验收条件。一张实施票、分支、PR 只对应一个归属目录。Skill 的跨层切片建议服从本仓库边界，跨目录依赖拆为不同票。
3. **按票执行**：选择依赖已满足、未完成且未被他人领取的票；执行前记录领取人及状态。开发票显式使用 `implement`，先核对工作区，按 Git 约定建立或复用合适分支 / worktree，不覆盖未提交文件。评测、设计、文档票交付对应产物；评测票需要编写运行代码时也使用 `implement`。
4. **验证与审查**：记录实际运行、结果、产物与 PR 链接。有代码时使用 `code-review`，分别核对规范和票据；AI 审查、CI 通过和真人批准分别记录，不能互相替代。非代码票按 spec 验收其交付物。
5. **更新进度**：每票完成后更新票据与对应项目跟踪；待真实验收通过后再收口包。涉及里程碑完成时先更新该版本 `completion.md`，再启动下一版本。

拆票前在 spec 中列出带编号的核心场景及测试覆盖框架；拆票时按[票据模板](issue-tracker.md)关联场景并写本票验证要求，安排有明确依赖的联调验收及全面评测票。按票执行时先验证局部能力，再验证受影响的核心路径；路径就绪即联调，阶段结束再做全面验收，具体要求引用上述规则。

完成条件：每张完成票都有可检查的交付证据，没有把占位、stub 验证或单模块通过记成端到端完成；核心路径通过与阶段完整验收分别记录。

## 5. 队员可直接使用的开工指令

```text
我是【姓名】，请读取 AGENTS.md 和队员开工规范，查找正式分派给我的可领取交付包，先告诉我包名、范围、依赖和验收要求。
```

队员确认后：

```text
我确认领取【交付包及本人工作线】，请自动记录领取，检查并安装缺失的通用 Skill，按 to-spec → to-tickets 流程推进；有开发票时再用 implement 按票执行。需要我判断的具体范围或验收问题就在本任务讨论。
```

例如 2026-10-11 的 v0.4：周恩宇可领取 [v04-bills/01 账单业务能力与评测](../../.scratch/v04-bills/packages/01-bills-backend.md)（ready，接包即拆票）；Ringo 或 PM 代行可领取 [v04-security/01 检测器与评测完整性](../../.scratch/v04-security/packages/01-detector-and-coverage.md)；梁爽、六水的 [frontend-complete/01 完整前端](../../.scratch/frontend-complete/packages/01-v04-complete-frontend.md) 等原型走查确认后领取。
