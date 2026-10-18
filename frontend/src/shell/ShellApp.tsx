import { useMemo } from "react";
import { AdminDemoPage } from "./AdminDemoPage";
import { AssistantPage } from "./AssistantPage";
import { GalleryPage } from "./GalleryPage";
import { createSlotRegistry } from "./slots";
import { createRealDataSource } from "./api/realDataSource";
import { transferSlot } from "./slots/transferDemoSlot";
import { createDemoBackend } from "./stub/demoBackend";
import "./shell.css";

export default function ShellApp() {
  const backend = useMemo(() => createDemoBackend(), []);
  const realSource = useMemo(() => createRealDataSource(), []);
  const slots = useMemo(() => createSlotRegistry([transferSlot]), []);
  const path = window.location.pathname;
  if (path.startsWith("/v04/admin")) return <AdminDemoPage admin={backend.admin} stubExtras={backend.admin} />;
  if (path.startsWith("/v04/gallery")) return <GalleryPage />;
  return <AssistantPage source={import.meta.env.VITE_API_MODE === "contract-demo" ? backend.user : realSource} slots={slots} />;
}
