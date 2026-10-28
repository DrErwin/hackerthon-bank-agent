# v05-cross-business/14: align S05 with the actual child pause explanation

Ticket ID: v05-cross-business/14
Package: [v05-cross-linkage/packages/03-cross](../../v05-cross-linkage/packages/03-cross.md)
Spec: [Cross14 minimal assertion specification](../14-unknown-child-assertion-spec.md)
Core scenarios: UA01-UA03 in the specification
Type: development (test maintenance only)
Owner: Erwin (v0.5); implementation: bank_reset_completion AI subagent
Directory: backend/app/modules/cross/
Status: in_progress
Blocked by: None (PR349 behavior is already on main)
Accepted by: Erwin through the user's continued authorization and root's assignment
Accepted at: 2026-10-28
Branch: codex/v05-cross-unknown-assertion-14
Verification: Preserve unchanged S05 red, then rerun only S05 and direct S01/S04 neighbors. Record source/hash and unchanged production manifest; no full suite/model/page/shared bank.

- [ ] Existing S05 reproduces the stale assertion before maintenance.
- [ ] Parent asserts the actual child public pause/unknown explanation and stops other work.
- [ ] All original state, bank, partial-success and duplicate-call assertions remain.
- [ ] The final local set passes and backend production equality is recorded.
- [ ] Root independently reviews and merges; original full-backend failure remains historical evidence.
