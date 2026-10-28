# Cross14: maintain the S05 public unknown-result assertion

Status: implemented_pending_review
Owner: Erwin (v0.5); implementation: bank_reset_completion AI subagent
Accepted by: Erwin through the user's continued non-material task and root's explicit assignment
Accepted at: 2026-10-28
Directory: backend/app/modules/cross/
Package: [v05-cross-linkage/packages/03-cross](../v05-cross-linkage/packages/03-cross.md)
Ticket: [v05-cross-business/14](issues/14-unknown-child-assertion.md)
Base: bb6228bd6f96b8c5aaf2dd43abcd659da01bed86

## Problem and approved behavior

The existing S05 test still expects the generic words "结果未知" and "核实原操作"
in its parent card. PR349 deliberately changed that card to reuse the actual
child's public paused explanation. The child still needs attention, the parent
still runs, and other work must remain stopped until the original result is known.

The [PR349 specification](paused-summary-12.md) PC01-PC03 requires the real public
child explanation and preserves states, queries and stop behavior. Maintain this
test's assertions against that agreed behavior; do not remove uncertainty coverage
or restore the older production wording.

Root's full-backend batch remains 2570 passed / 13 skipped / 1 failed at bb6228bd.
Its original XML SHA256 is 23ee3fe65fa28d8832477bf25a73f3ddd3990d68fca8304f4cf1175990d01eb6.
This ticket cannot relabel that batch as passing or combine local reruns into a
single new full-backend result.

## Core scenarios and verification

| ID | Existing public scenario | Required evidence |
|---|---|---|
| UA01 | S05 second child is needs_attention | Parent RUNNING, same child explanation, public uncertainty/query warning and no later work |
| UA02 | Resume/stop S05 after one success | Original no-redispatch, bank calls, partial success and savings assertions remain intact |
| UA03 | Direct neighboring normal/cancel paths | Existing S01 and S04 still pass |

First run the unchanged S05 node and preserve its red XML. Then change only its
two obsolete wording assertions, retaining every other original assertion and
adding checks for the actual public child's pause reason and continuation stop.
Run only S05 and the direct S01/S04 neighbors, using fresh isolated local test data.
The existing PlannerStub/FakeSubscriptionBank remain explicit test substitutes;
this is not real-model, HTTP, browser or shared-bank acceptance.

## Boundaries

Only the one test and this ticket's scratch files may change. Production files,
fixtures, helpers, expected bank effects, partial-success facts and duplicate-call
checks are frozen. Record exact source/XML hashes and a reproducible backend
manifest excluding only the one changed test, so production equality is auditable.
Root arranges independent Standards/Spec review, CI checks and merge.
