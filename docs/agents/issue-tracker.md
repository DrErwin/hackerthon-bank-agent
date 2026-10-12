# Issue tracker: Local Markdown

Issues and specs for this repo live as markdown files in `.scratch/`.

## Conventions

- One feature per directory: `.scratch/<feature-slug>/`
- The spec is `.scratch/<feature-slug>/spec.md`
- Implementation issues are one file per ticket at `.scratch/<feature-slug>/issues/<NN>-<slug>.md`, numbered from `01` — never a single combined tickets file
- Triage state is recorded as a `Status:` line near the top of each issue file
- Comments and conversation history append to the bottom of the file under a `## Comments` heading

## 交付包与票据标识（2026-09-30 确认）

**按文件夹分别编号，完整票号在项目内唯一。** 每组规格和实施票使用一个固定的 `<feature-slug>`；组内编号从 `01` 开始，追加票使用本组下一个未使用编号。不同组可以同时有 `01`，无需集中申请全项目流水号。

| 对象 | 完整标识与写法 | 作用 |
|---|---|---|
| 交付包 | 文件在 `.scratch/` 下的相对路径，去掉 `.md`，例如 `transfer-agent-framework/packages/01-vertical-backend` | 业务范围、负责人、开始条件与联合验收 |
| 实施票 | `<feature-slug>/<NN>`，例如 `v03-session-recovery-reply/01` | 一个目录内的具体交付和验收 |
| GitHub 问题 | `Issue #23`，附 Issue 链接 | 缺口、争议或需求问题记录 |
| GitHub 交付 | `PR #27`，附 PR 链接 | 代码或文档差异、审查与合并记录 |

### 创建与归属

- 新工作组标识使用小写英文、数字和连字符，优先表达里程碑与工作内容，例如 `v03-session-recovery-reply`。创建前核对 `.scratch/`，同一组规格继续追加，不重复建立；独立工作组使用不同标识。
- 每位负责人在交付包下建立自己的工作组；多人共享同一交付包时，各工作组分别指向原包。一人负责多个独立工作组也分别编号，归属由 `Owner` 与交付包链接表达。
- 新票显式写 `Ticket ID`、`Package`（完整交付包标识、标题及链接）、`Spec`、`Owner`、`Directory`、`Status` 和 `Blocked by`。编号对应文件名前缀，仍保持一票一文件、一票一实施目录。
- 已发布的工作组标识、票号和交付包路径保持稳定。负责人变更只更新 `Owner`；标题可更新，保留原路径和编号。已取消或废弃的票保留记录，编号不再复用。
- 现有带人名的工作组文件夹保留，不批量重命名；旧票缺少显式 ID 时按所在文件夹和编号识别，后续编辑时补字段。现有十二张票与恢复 / 仅回复六张票继续使用各自目录内编号。

### GitHub 问题的归属（2026-10-12 项目负责人要求）

- **新建 GitHub Issue 必须在正文顶部写明转给谁**，格式行：`转给: <姓名>`。没有明确接收人的 Issue 不建；先确定归属再建，不写“待定”“大家看”。
- 有仓库写权限时同时设置 GitHub Assignee，与正文的 `转给:` 保持一致；团队成员 GitHub 账号尚未全部加入仓库时，用姓名写明即可，由有权限者代设，不因此跳过归属行。
- 一个 Issue 对应一个接收人；需要多人协作时在正文写清分工，不把归属留给读者推断。
- 转派或关闭时同步更新正文 `转给:` 行与 Assignee。归属只表示“谁负责推进或落地”，Issue 本身不会通知责任人，可执行动作仍须在 `docs/01-项目跟踪.md` 或飞书进度表登记。

### 引用与依赖

- 聊天、项目跟踪、跨组依赖、交接和 PR 使用“**完整票号＋标题＋链接**”；例如 [v03-session-recovery-reply/01：原任务的新会话归属转换](../../.scratch/v03-session-recovery-reply/issues/01-task-session-transition.md)。
- 同组文档内可以用本地编号简称，但必须能从本文件所在工作组确定归属；跨组 `Blocked by` 使用完整票号、标题和链接。接到只写“票 01”且不能确定工作组的指令时，先定位交付包 / spec；仍有歧义再询问，不凭数字选择任务。
- `Blocked by` 表示实施前置票；GitHub 缺口记为 `Source issue: Issue #23`，关联交付记为 `PR #n`，各自附链接。前置实现票满足依赖须有公开能力及合入证据，问题记录或补票文档本身不表示能力已提供。
- PR 正文写完整实施票引用；有前置 PR 时另写 `Depends on PR #n`。一个问题可以拆成多张票，每张实施票按目录独立交付；补票文档 PR 可以集中发布已确认的票据。

新票字段示例（尖括号为占位符，复制时替换）：

```text
Ticket ID: <feature-slug>/<NN>
Package: <完整交付包标识>：<标题>（附交付包链接）
Spec: <本工作组 spec 链接>
Core scenarios: <核心场景编号及场景 spec 链接；不适用时说明原因>
Verification: <本票验收步骤、预期结果、证据要求及受影响的核心路径>
Owner: <负责人>
Directory: <单一实施目录>
Status: <当前状态>
Blocked by: <完整前置票号、标题及链接；无则写 None>
Source issue: Issue #<编号>（有来源问题时附链接）
```

完成检查：每张新票可由完整票号定位到唯一文件，所属交付包与 spec 可读，所有跨组依赖可定位，票号、Issue 和 PR 没有混用。

`Core scenarios` 引用场景 spec 中的稳定编号，不在每张票复制完整场景。`Verification` 区分本票局部验收与整条路径验收；尚未具备的路径由明确依赖的联调验收票覆盖，不把局部通过标为场景通过。非业务票不适用时写明原因。

拆票时明确联调验收及阶段全面评测的责任与依赖，已有对应票时复用。联调票只负责验证与证据，跨目录缺陷分别回到所属实施票修复；验收顺序和完成门槛见[跨团队交付原则 §3](../principles/04-cross-team-delivery.md#3-标准流程)。

## When a skill says "publish to the issue tracker"

Create a new file under `.scratch/<feature-slug>/` (creating the directory if needed).

## When a skill says "fetch the relevant ticket"

Read the file at the referenced path. The user will normally pass the path or the issue number directly.

Resolve local ticket references using the complete ID above. A GitHub `Issue #n` is a problem record, not a local ticket number; follow its linked spec/tickets before implementation.

## Wayfinding operations

Used by `/wayfinder`. The **map** is a file with one **child** file per ticket.

- **Map**: `.scratch/<effort>/map.md` — the Notes / Decisions-so-far / Fog body.
- **Child ticket**: `.scratch/<effort>/issues/NN-<slug>.md`, numbered from `01`, with the question in the body. A `Type:` line records the ticket type (`research`/`prototype`/`grilling`/`task`); a `Status:` line records `claimed`/`resolved`.
- **Blocking**: a `Blocked by: NN, NN` line near the top. A ticket is unblocked when every file it lists is `resolved`.
- **Frontier**: scan `.scratch/<effort>/issues/` for files that are open, unblocked, and unclaimed; first by number wins.
- **Claim**: set `Status: claimed` and save before any work.
- **Resolve**: append the answer under an `## Answer` heading, set `Status: resolved`, then append a context pointer (gist + link) to the map's Decisions-so-far in `map.md`.

## Not this repo's task tracker

Team task assignment and progress live elsewhere and are not part of this convention:

- `docs/01-项目跟踪.md` — 协作流程、官方节点与开放问题
- 飞书多维表格（文档内嵌） — 任务负责人与状态的实际维护处
- `docs/pm/ROADMAP.md` — 六阶段规划与硬依赖

`.scratch/` holds engineering tickets and specs for agent-driven work; it does not replace the above.

## Cross-team vertical scenarios

For a scenario that spans multiple owned directories:

- The scenario lead creates one shared `.scratch/<scenario>/spec.md`.
- The scenario lead creates owner-level handoff packages under `.scratch/<scenario>/packages/`.
- A package fixes the business outcome, start condition, dependencies and acceptance; it does not prescribe another owner's internal code tickets.
- After accepting a package, each directory owner creates their own feature directory and detailed tickets under `.scratch/<owner-feature>/issues/`.
- Every implementation ticket still changes only one owned directory.

After explicit acceptance, the AI records the actual person, date and workstream in the package and project tracking entry, checks the common skills, then follows `to-spec → to-tickets → ticket execution` (`implement` for coding tickets). Reuse existing specs and tickets. See [delivery workflow and common skills](delivery-workflow.md) for the record fields, installation checks and completion criteria.

The package file does not assign or notify anyone. Activation, owner, dates and team-visible status remain in `docs/01-项目跟踪.md` and the Feishu progress table. Full workflow: [cross-team delivery principle](../principles/04-cross-team-delivery.md).
