import { useMemo } from "react";
import { API_MODE, type ApiMode } from "../api";
import { AdminDemoPage } from "./AdminDemoPage";
import { AssistantPage } from "./AssistantPage";
import { GalleryPage } from "./GalleryPage";
import { createSlotRegistry } from "./slots";
import { createRealDataSource } from "./api/realDataSource";
import { billsSlot } from "./slots/billsSlot";
import { transferSlot } from "./slots/transferDemoSlot";
import { createDemoBackend } from "./stub/demoBackend";
import "./shell.css";

export function shellUsesContractDemo(mode: ApiMode = API_MODE): boolean {
  return mode === "contract-demo";
}

export default function ShellApp() {
  const backend = useMemo(() => createDemoBackend(), []);
  const realSource = useMemo(() => createRealDataSource(), []);
  const slots = useMemo(() => createSlotRegistry([transferSlot, billsSlot]), []);
  const path = window.location.pathname;
  if (path.startsWith("/v04/admin")) return <AdminDemoPage admin={backend.admin} stubExtras={backend.admin} />;
  if (path.startsWith("/v04/gallery")) return <GalleryPage />;
  return <AssistantPage source={shellUsesContractDemo() ? backend.user : realSource} slots={slots} />;
}
