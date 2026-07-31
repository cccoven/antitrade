import { useState, useEffect } from "react";
import { NavLink, useLocation } from "react-router-dom";
import {
  LayoutDashboard,
  BookOpen,
  FlaskConical,
  PanelLeftClose,
  Settings2,
  UserIcon,
  Wallet,
  BookMarked,
  Sparkles,
  Radar,
  Wrench,
  Workflow,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { cn } from "@/lib/utils";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  Sidebar as SidebarRoot,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar";
import SidebarUserMenu from "./SidebarUserMenu";
import NotificationInbox from "./NotificationInbox";
import { useAuth } from "@/auth/auth-context";
import {
  handleWindowDragDoubleClick,
  handleWindowDragMouseDown,
} from "@/lib/window-chrome";

const navItems = [
  { path: "/", labelKey: "nav.workspace", icon: LayoutDashboard },
  { path: "/assistant", labelKey: "nav.assistant", icon: Sparkles },
  { path: "/automations", labelKey: "nav.automations", icon: Workflow },
  { path: "/radar", labelKey: "nav.radar", icon: Radar },
  { path: "/tools", labelKey: "nav.tools", icon: Wrench },
  { path: "/journal", labelKey: "nav.journal", icon: BookOpen },
  { path: "/strategies", labelKey: "nav.strategies", icon: BookMarked },
  { path: "/portfolio", labelKey: "nav.portfolio", icon: Wallet },
  { path: "/backtest", labelKey: "nav.backtest", icon: FlaskConical },
] as const;

export default function Sidebar() {
  const { t } = useTranslation();
  const location = useLocation();
  const { state, toggleSidebar } = useSidebar();
  const collapsed = state === "collapsed";
  const [settingsHover, setSettingsHover] = useState(false);
  const [loginHover, setLoginHover] = useState(false);
  const { user, setLoginDialogOpen } = useAuth();

  useEffect(() => {
    setSettingsHover(false);
    setLoginHover(false);
  }, [collapsed]);

  return (
    <SidebarRoot collapsible="icon">
      <div
        className="sidebar-window-drag-region"
        data-window-drag-region
        onMouseDown={handleWindowDragMouseDown}
        onDoubleClick={handleWindowDragDoubleClick}
      />
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>{t("sidebar.navigation")}</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {navItems.filter((item) => !("hidden" in item && item.hidden)).map((item) => {
                const Icon = item.icon;
                const label = t(item.labelKey);
                const isActive =
                  item.path === "/"
                    ? location.pathname === "/"
                    : location.pathname.startsWith(item.path);

                return (
                  <SidebarMenuItem key={item.path}>
                    <SidebarMenuButton asChild tooltip={label} isActive={isActive}>
                      <NavLink to={item.path} end={item.path === "/"}>
                        <Icon />
                        <span>{label}</span>
                      </NavLink>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                );
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter>
        <div className="sidebar-footer-row">
          {user ? (
            <SidebarUserMenu collapsed={collapsed} />
          ) : (
            <Tooltip open={collapsed && loginHover}>
              <TooltipTrigger asChild>
                <button
                  type="button"
                  className="sidebar-settings-btn"
                  onClick={() => setLoginDialogOpen(true)}
                  onMouseEnter={() => setLoginHover(true)}
                  onMouseLeave={() => setLoginHover(false)}
                >
                  <UserIcon />
                  <span className="sidebar-settings-label">{t("auth.login")}</span>
                </button>
              </TooltipTrigger>
              <TooltipContent side="right">{t("auth.login")}</TooltipContent>
            </Tooltip>
          )}
        </div>
        {user ? (
          <div className="sidebar-footer-row">
            <NotificationInbox collapsed={collapsed} />
          </div>
        ) : null}
        <div className="sidebar-footer-row">
          <Tooltip open={collapsed && settingsHover}>
            <TooltipTrigger asChild>
              <NavLink
                to="/settings"
                className={cn("sidebar-settings-btn", location.pathname.startsWith("/settings") && "is-active")}
                onMouseEnter={() => setSettingsHover(true)}
                onMouseLeave={() => setSettingsHover(false)}
              >
                <Settings2 />
                <span className="sidebar-settings-label">{t("sidebar.settings")}</span>
              </NavLink>
            </TooltipTrigger>
            <TooltipContent side="right">{t("sidebar.settings")}</TooltipContent>
          </Tooltip>

          <button onClick={toggleSidebar} className="sidebar-toggle-btn">
            <PanelLeftClose className={cn("sidebar-toggle-icon", collapsed && "is-collapsed")} />
          </button>
        </div>
      </SidebarFooter>
    </SidebarRoot>
  );
}
