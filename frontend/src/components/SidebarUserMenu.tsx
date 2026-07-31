import { useEffect, useState } from "react";
import { UserIcon, LogOut } from "lucide-react";
import { useTranslation } from "react-i18next";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { useAuth } from "@/auth/auth-context";

interface SidebarUserMenuProps {
  collapsed: boolean;
}

export default function SidebarUserMenu({ collapsed }: SidebarUserMenuProps) {
  const { t } = useTranslation();
  const { user, logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const [menuHover, setMenuHover] = useState(false);

  useEffect(() => {
    setMenuHover(false);
  }, [collapsed]);

  if (!user) return null;

  const handleLogout = () => {
    setMenuOpen(false);
    logout();
  };

  return (
    <DropdownMenu open={menuOpen} onOpenChange={setMenuOpen}>
      <Tooltip open={collapsed && !menuOpen && menuHover}>
        <TooltipTrigger asChild>
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              className={cn("sidebar-settings-btn", menuOpen && "is-active")}
              onMouseEnter={() => setMenuHover(true)}
              onMouseLeave={() => setMenuHover(false)}
            >
              <UserIcon />
              <span className="sidebar-settings-label">{user.name}</span>
            </button>
          </DropdownMenuTrigger>
        </TooltipTrigger>
        <TooltipContent side="right">{user.name}</TooltipContent>
      </Tooltip>
      <DropdownMenuContent
        side={collapsed ? "right" : "top"}
        align={collapsed ? "end" : "start"}
        sideOffset={12}
        className="min-w-[14rem]"
      >
        <DropdownMenuLabel className="flex flex-col gap-0.5">
          <span
            className="text-foreground font-medium"
            style={{ fontSize: "var(--font-ui)" }}
          >
            {user.name}
          </span>
          <span
            className="text-muted-foreground"
            style={{ fontSize: "var(--font-caption)" }}
          >
            {user.email}
          </span>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={handleLogout}>
          <LogOut />
          {t("auth.logout")}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
