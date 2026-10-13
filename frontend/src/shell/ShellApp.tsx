import { useMemo } from "react";
import { AdminDemoPage } from "./AdminDemoPage";
import { AssistantPage } from "./AssistantPage";
import { GalleryPage } from "./GalleryPage";
import { createSlotRegistry } from "./slots";
import { transferDemoSlot } from "./slots/transferDemoSlot";
import { createDemoBackend } from "./stub/demoBackend";
import "./shell.css";

export default function ShellApp() {
  const backend = useMemo(() => createDemoBackend(), []);
  const slots = useMemo(() => createSlotRegistry([transferDemoSlot]), []);
  const path = window.location.pathname;
  if (path.startsWith("/v04/admin")) return <AdminDemoPage admin={backend.admin} stubExtras={backend.admin} />;
  if (path.startsWith("/v04/gallery")) return <GalleryPage />;
  return <AssistantPage source={backend.user} slots={slots} />;
}
