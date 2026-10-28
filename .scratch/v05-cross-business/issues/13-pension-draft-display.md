# v05-cross-business/13: correct pension draft availability prompts

Ticket ID: v05-cross-business/13
Package: [v05-cross-linkage/packages/03-cross](../../v05-cross-linkage/packages/03-cross.md)
Spec: [Cross13 minimal display specification](../13-pension-draft-display-spec.md)
Core scenarios: PD01-PD04 in the specification
Type: development
Owner: Erwin (v0.5); implementation: bank_reset_completion AI subagent
Directory: backend/app/modules/cross/
Status: merged — PR354, 58ab51584dfd9e8dc7289eb0924594c42fe21e03
Blocked by: None (the current pension flow and public test seam are on main)
Accepted by: Erwin through the user's authorization and root's explicit assignment
Accepted at: 2026-10-28
Branch: codex/v05-pension-draft-display-13
Verification: Preserve the initial red result, then targeted public prompt and existing pension branch results with exact source, tree and raw XML hashes. No model, browser, shared-bank or full-suite runs.

## Acceptance

- [x] Destination and next-amount prompts show 1000 after selecting 2500, then zero after another 1000.
- [x] Revising the current allocation excludes its own old amount; successful allocations are counted only once.
- [x] Original execution range, money checks, input grammar, gates and profile are unchanged.
- [x] Red/green and fixed-source evidence are recorded without replacing historical results.
- [x] Root Standards and independent Spec both have zero must-fix items; exact-head CI was billing-blocked before startup. Root merged PR354; no author merge or human acceptance claim.

## Comments

2026-10-28: The managed worktree and branch already existed from the previous
turn at bec56218, clean and without implementation files; they were reused.
Original public-prompt red: 1 failed / 10.90s at f2794d7f. Final exact local set:
10 passed / 25.00s at dae4c1e3. Three intervening synthetic checkpoint setup
failures are preserved and classified separately, not erased or called product
failures. [Sources, raw XML hashes and boundaries](../13-pension-draft-display-verification.md).
