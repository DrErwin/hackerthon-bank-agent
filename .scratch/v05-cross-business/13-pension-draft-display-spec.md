# Cross13: show the unallocated pension draft amount

Status: in_progress
Owner: Erwin (v0.5); implementation: bank_reset_completion AI subagent
Accepted by: Erwin through the user's non-material completion authorization and root's explicit Cross13 assignment
Accepted at: 2026-10-28 (resuming the approved 2026-10-27 scope)
Directory: backend/app/modules/cross/
Base: bec5621800dd58ec1c24ac224fd3008bba3f0ff4
Package: [v05-cross-linkage/packages/03-cross](../v05-cross-linkage/packages/03-cross.md)
Ticket: [v05-cross-business/13](issues/13-pension-draft-display.md)

## Problem and solution

The actual P01 HTTP batch shows 3500 yuan as still available after the customer
has already selected 2500 yuan, and again after selecting the final 1000 yuan.
The final summary correctly totals 3500 yuan. The two draft prompts must show
the amount not yet assigned in the draft: 1000 yuan, then zero.

The original [57-line batch](../v05-control/evidence/2026-10-27-http-live-40cedee160da-pension-completed.jsonl.gz)
remains unchanged; its original source is 5278f870, not this fix.

## Implementation decisions

- Change only the destination and current-amount prompts in the pension flow.
- Start from the existing remaining execution range, which already counts
  successful transfers. Subtract filled draft allocations that have not succeeded.
- The destination prompt counts every such allocation. The amount prompt omits
  the current allocation's old amount so revising it does not subtract it twice.
- An unfinished or failed old allocation remains a draft amount. Successful
  allocations are never counted twice. Negative historical drafts are not clamped.
- Do not change amount acceptance, adoption, preflight, confirmation, verification,
  bank rules, risk facts, or the approved P01 profile. Add no aggregate rejection.
- No schema, API, capability, permissions or side effects change. Existing
  per-transfer confirmation and execution authorization remain the only write path.

## Core scenarios and testing

| ID | Scenario | Expected public prompt |
|---|---|---|
| PD01 | 5000 scope, 1500 retained, first draft 2500 | Destination and next amount show 1000 |
| PD02 | Add the second draft 1000 | Destination shows zero; adoption still totals 3500 |
| PD03 | Resume an amount question containing its own previous 1000 | Editable capacity is 1000, not zero; changing to 900 leaves 100 |
| PD04 | An earlier 2500 allocation is already successful | Count that success only once; the next amount still shows 1000 |

Tests observe CrossEntry start/resume results. Existing contract-shaped test
children are explicit substitutes; restored checkpoint cases are synthetic local
fixtures. They are not actual bank, model, HTTP or browser acceptance.
First preserve a failing public-prompt regression, then fix the display, then run
only the new tests and the existing pension normal/amount/preflight branches.
Root owns independent Standards/Spec review, final integration and merge.

## Out of scope and workflow notes

Birthday recovery, shared data, model/browser runs, full suites, new money policy,
operator seeds and competition material are excluded. No file overlaps Cross09.
The existing to-spec/to-tickets/implement files were read and checked; they disable
model invocation and are not reported as slash-command calls. The assigned
single-ticket scope and existing public test seam were explicitly approved by root.
