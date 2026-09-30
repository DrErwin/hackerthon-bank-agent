# Issue tracker: Local Markdown

Issues and specs for this repo live as markdown files in `.scratch/`.

## Conventions

- One feature per directory: `.scratch/<feature-slug>/`
- The spec is `.scratch/<feature-slug>/spec.md`
- Implementation issues are one file per ticket at `.scratch/<feature-slug>/issues/<NN>-<slug>.md`, numbered from `01` — never a single combined tickets file
- Triage state is recorded as a `Status:` line near the top of each issue file
- Comments and conversation history append to the bottom of the file under a `## Comments` heading

## When a skill says "publish to the issue tracker"

Create a new file under `.scratch/<feature-slug>/` (creating the directory if needed).

## When a skill says "fetch the relevant ticket"

Read the file at the referenced path. The user will normally pass the path or the issue number directly.

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
