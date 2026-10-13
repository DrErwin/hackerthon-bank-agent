import type { ReactNode } from "react";
import type { DisplayField, ModuleError, ResultView, ShellTask } from "./types";

export interface SlotAction {
  label: string;
  onClick: () => void;
}

export interface BusinessSlot<D = unknown> {
  module: string;
  label: string;
  voiceDemoText?: string;
  exampleHints?: string[];
  confirmTitle?: string;
  emphasizeField?: string;
  // Facts already returned by the server, shown on waiting / recovery / needs_attention cards.
  summarize?: (task: ShellTask<D>) => DisplayField[];
  result?: (task: ShellTask<D>) => ResultView | null;
  errorHint?: (error: ModuleError, task: ShellTask<D>) => ReactNode;
  confirmationActions?: (task: ShellTask<D>) => SlotAction[];
}

export const genericSlot: BusinessSlot = {
  module: "generic",
  label: "业务",
};

export function createSlotRegistry(slots: BusinessSlot<never>[]) {
  const byModule = new Map(slots.map((slot) => [slot.module, slot as BusinessSlot]));
  return {
    slots: [...byModule.values()],
    resolve(module: string | null): BusinessSlot {
      return (module && byModule.get(module)) || genericSlot;
    },
  };
}

export type SlotRegistry = ReturnType<typeof createSlotRegistry>;
