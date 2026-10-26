import { useEffect, useState, type ReactNode } from "react";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetClose, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Drawer, DrawerClose, DrawerContent, DrawerTitle, DrawerTrigger } from "@/components/ui/drawer";

export function DetailsDrawer({ title, children, onOpenChange, open: controlledOpen, triggerLabel, onCloseAutoFocus }: {
  title: string; children: ReactNode; onOpenChange?: (open: boolean) => void; open?: boolean; triggerLabel?: ReactNode;
  onCloseAutoFocus?: (event: Event) => void;
}) {
  const [localOpen, setOpen] = useState(false);
  const open = controlledOpen ?? localOpen;
  const [desktop, setDesktop] = useState(window.innerWidth >= 960);
  useEffect(() => {
    const resize = () => setDesktop(window.innerWidth >= 960);
    window.addEventListener("resize", resize);
    return () => window.removeEventListener("resize", resize);
  }, []);
  function change(next: boolean) { setOpen(next); onOpenChange?.(next); }
  const trigger = <Button type="button" variant="link" className="sh-detail-trigger">{triggerLabel ?? title}</Button>;
  const close = <Button type="button" variant="outline" size="sm"><X aria-hidden="true" />关闭详情</Button>;
  return desktop ? (
    <Sheet open={open} onOpenChange={change}>
      <SheetTrigger asChild>{trigger}</SheetTrigger>
      <SheetContent className="sh-detail-surface" showCloseButton={false} aria-describedby={undefined} onCloseAutoFocus={onCloseAutoFocus}>
        <header className="sh-detail-head"><SheetTitle>{title}</SheetTitle><SheetClose asChild>{close}</SheetClose></header>
        <div className="sh-drawer-body">{children}</div>
      </SheetContent>
    </Sheet>
  ) : (
    <Drawer open={open} onOpenChange={change} autoFocus repositionInputs={false}>
      <DrawerTrigger asChild>{trigger}</DrawerTrigger>
      <DrawerContent className="sh-detail-surface" aria-describedby={undefined} onCloseAutoFocus={onCloseAutoFocus}>
        <header className="sh-detail-head"><DrawerTitle>{title}</DrawerTitle><DrawerClose asChild>{close}</DrawerClose></header>
        <div className="sh-drawer-body">{children}</div>
      </DrawerContent>
    </Drawer>
  );
}
