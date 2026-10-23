// Demo-only slot proving the shell can host a business line. Ticket 03 replaces it with the
// full transfer slot; it must stay a pure mapper of server-returned TransferTaskView fields.
import type { TransferTaskView } from "../../contracts";
import { yuan } from "../format";
import type { BusinessSlot } from "../slots";
import type { DisplayField, ResultView, ShellTask } from "../types";

function payeeText(data: TransferTaskView): string | null {
  return data.payee ? data.payee.name_masked + "（" + data.payee.account_masked + "）" : null;
}

function summarize(task: ShellTask<TransferTaskView>): DisplayField[] {
  const data = task.data;
  if (!data) return [];
  const fields: DisplayField[] = [];
  const payee = payeeText(data);
  if (payee) fields.push({ name: "payee", label: "收款人", value_text: payee });
  if (typeof data.amount_fen === "number") fields.push({ name: "amount", label: "金额", value_text: yuan(data.amount_fen) });
  return fields;
}

function result(task: ShellTask<TransferTaskView>): ResultView | null {
  const operation = task.data?.operation;
  if (task.status === "cancelled") {
    return { tone: "neutral", title: "已取消，没有转出", fields: summarize(task) };
  }
  if (task.status === "failed" && !operation) {
    return { tone: "danger", title: task.data && "amount_fen" in task.data ? "这笔转账没有完成" : "这次查询没有完成", fields: summarize(task) };
  }
  if (!operation) return null;
  if (operation.operation_status === "succeeded" && operation.receipt) {
    const receipt = operation.receipt;
    return {
      tone: "success",
      title: "转账成功",
      headline: yuan(receipt.amount_fen),
      fields: [
        { name: "payee", label: "收款人", value_text: receipt.payee.name_masked + "（" + receipt.payee.account_masked + "）" },
        { name: "bank", label: "收款银行", value_text: receipt.payee.bank_name },
        { name: "fee", label: "手续费", value_text: yuan(receipt.fee_fen) },
        { name: "transaction", label: "交易号", value_text: receipt.transaction_id },
      ],
    };
  }
  if (operation.operation_status === "failed") {
    return {
      tone: "danger",
      title: "这笔钱没有转出去",
      fields: [...summarize(task), { name: "reason", label: "银行说明", value_text: task.error?.reason || "银行未批准这笔转账，请核对账户、金额和收款资料。" }],
    };
  }
  return null;
}

export const transferSlot: BusinessSlot<TransferTaskView> = {
  module: "transfer",
  label: "转账",
  voiceDemoText: "转给妈妈500块",
  exampleHints: ["转给妈妈 500 块", "给张阿姨转 200 元"],
  confirmTitle: "请确认这笔转账",
  emphasizeField: "amount",
  canModifyConfirmation: true,
  summarize,
  result,
};
