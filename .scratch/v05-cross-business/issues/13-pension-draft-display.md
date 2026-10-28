# v05-cross-business/13: correct pension draft availability prompts

Ticket ID: v05-cross-business/13
Package: [v05-cross-linkage/packages/03-cross](../../v05-cross-linkage/packages/03-cross.md)
Spec: [Cross13 minimal display specification](../13-pension-draft-display-spec.md)
Core scenarios: PD01-PD04 in the specification
Type: development
Owner: Erwin (v0.5); implementation: bank_reset_completion AI subagent
Directory: backend/app/modules/cross/
Status: in_progress
Blocked by: None (the current pension flow and public test seam are on main)
Accepted by: Erwin through the user's authorization and root's explicit assignment
Accepted at: 2026-10-28
Branch: codex/v05-pension-draft-display-13
Verification: Preserve the initial red result, then targeted public prompt and existing pension branch results with exact source, tree and raw XML hashes. No model, browser, shared-bank or full-suite runs.

## Acceptance

- [ ] Destination and next-amount prompts show 1000 after selecting 2500, then zero after another 1000.
- [ ] Revising the current allocation excludes its own old amount; successful allocations are counted only once.
- [ ] Original execution range, money checks, input grammar, gates and profile are unchanged.
- [ ] Red/green and fixed-source evidence are recorded without replacing historical results.
- [ ] Root arranges independent two-axis review and CI/merge verification; no author merge or human acceptance claim.
