import { useState } from "react";
import Sidebar from "./Sidebar";
import { cn } from "@/lib/utils";
import { isTauriShell } from "@/lib/window-chrome";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";
import { readSidebarCollapsed, writeSidebarCollapsed } from "../state/ui-storage";

interface AppShellProps {
  children: React.ReactNode;
}

export default function AppShell({ children }: AppShellProps) {
  const [collapsed, setCollapsed] = useState(() => readSidebarCollapsed(false));
  const tauriShell = isTauriShell();

  return (
    <SidebarProvider
      open={!collapsed}
      onOpenChange={(open) => {
        writeSidebarCollapsed(!open);
        setCollapsed(!open);
      }}
      className={cn("app-layout app-shell", collapsed && "is-collapsed")}
      style={
        {
          "--sidebar-width": "12rem",
          "--sidebar-width-icon": tauriShell ? "5.25rem" : "3rem",
        } as React.CSSProperties
      }
    >
      <Sidebar />
      <SidebarInset className="shell-main">
        <main className="shell-content">{children}</main>
      </SidebarInset>
    </SidebarProvider>
  );
}
