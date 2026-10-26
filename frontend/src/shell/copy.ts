// Approved user-visible copy for ticket v05-cross-frontend/02. Source of truth:
// `.scratch/v05-cross-frontend/copy-approval-2026-10-26.md`, where the owner replied
// 「可以」on 2026-10-26; every string below is that record verbatim, so a reviewer
// can audit the page's added wording in one place instead of picking it out of the
// components. Items 5 and 6 of the same record already live where their contract
// is: the two fallback error sentences in `useConversation.ts` (one per public
// error tier) and the birthday step names in `cross.ts` (`STEP_TITLE`).

// The quantity screen asks for a count; an amount example makes no sense there.
export const QUANTITY_HINT = "请填正整数，例如 2";

// Next to the options a confirmation/verification card publishes: the edit option
// returns to the same task's plan only while the old action was never submitted.
export const EDIT_OPTION_NOTE =
  "只有确认旧动作还没有真正提交，才会回到同一任务的方案；已提交或结果未知时，只能按原单号核实。";

// Above the delivery form: re-filling it places no order and moves no money.
export const DELIVERY_REFILL_NOTE = "重新填写不会下单，也不会扣款。";

// One sentence per delivery field, shown when that field is still blank.
export const DELIVERY_FIELD_REQUIRED = {
  recipient_name: "请填写收件人姓名。",
  phone: "请填写联系电话。",
  address: "请填写详细地址。",
} as const;
