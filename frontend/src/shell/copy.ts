// Shared user-visible copy. The original birthday copy approval is preserved in
// v05-cross-frontend/02; frontend-design-system/03 applies the user's approved
// concise, positive wording while retaining the same execution boundaries.

// The quantity screen asks for a count; an amount example makes no sense there.
export const QUANTITY_HINT = "请填正整数，例如 2";

// Next to the options a confirmation/verification card publishes: the edit option
// returns to the same task's plan only while the old action was never submitted.
export const EDIT_OPTION_NOTE =
  "修改前会核实办理进度；已提交的事项按原单号查看结果。";

// Above the delivery form: re-filling it places no order and moves no money.
export const DELIVERY_REFILL_NOTE = "请填写本次配送资料，选好商品后再核对订单。";

// One sentence per delivery field, shown when that field is still blank.
export const DELIVERY_FIELD_REQUIRED = {
  recipient_name: "请填写收件人姓名。",
  phone: "请填写联系电话。",
  address: "请填写详细地址。",
} as const;
