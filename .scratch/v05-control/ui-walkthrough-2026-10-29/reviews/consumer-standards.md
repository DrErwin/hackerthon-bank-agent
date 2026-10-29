# Standards review: API chat resume consumer

Reviewer: cross_resume_standards_review (non-author AI; not human acceptance)
Base: bbfb6fd045dd6070f2928d366519d492dfd37849 (merged provider PR357)
Reviewed implementation/test head: affd96d289f60841396b05e5e6729c960a3de2b1
Backend tree: 4a48fb693b3a4454b20d20bb66dc86a76478c5d6
API tree: 808951ea79c9081fe2a6dfd1762feb504999ea72

Result: 0 documented-standard violations; 0 actionable baseline smells.

Reviewed the fixed three-dot diff, full 256-line new API test file and surrounding original dispatch/continue_task gates under AGENTS.md, safety-platform and review/merge principles, issue-tracker rules and the code-review smell baseline. Only API production/test/README and separate consumer ticket/spec files differ from the merged provider. No provider implementation or shared contract was copied.

The four new service lines map resume explicitly to choice=resume after a current RUNNING/no-interaction check. Existing identity, thread, revision, recovery, allowed actions, pending verification and receipt handling remain. No recover_session or query fallback was introduced for resume. The minimum change reuses the deterministic continuation seam; there is no new abstraction, model execution authority or bank-rule copy.

Read eight integration tests: real Cross/Harness/ASGI HTTP/isolated MockBank with explicitly scripted planning. They cover same-parent continuation after a successful child, duplicate original UUID, interrupted internal receipt after progression, latest authoritative task projection changes, another thread, revision race, expired/new session and an UNKNOWN transfer that must not resubmit. The test-only inspection uses the real isolated runtime bank path and mode=ro, not the running demo bank.

git diff --check passed for the fixed base/head. The author test batch is still running; this review does not claim its result or a new independent pytest execution. Final PR evidence-only head must match the API tree above. Source review is clear; CI, fixed-head JUnit and actual page recovery remain separate root checks.

No running bank, model, browser, implementation, author working tree or external review comment was modified.
