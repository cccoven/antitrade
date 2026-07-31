import {
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
  type PointerEvent as ReactPointerEvent,
} from "react";
import { useTranslation } from "react-i18next";
import {
  ChevronDown,
  MessageSquare,
  MoreHorizontal,
  PanelLeftClose,
  PanelLeftOpen,
  Pencil,
  Pin,
  PinOff,
  Plus,
  Trash2,
} from "lucide-react";
import type { Conversation } from "@/api/client";
import { Button } from "@/components/ui/button";
import { TooltipIconButton } from "@/components/ui/tooltip-icon-button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import {
  assistantControlSizes,
  assistantHistoryPanel,
  assistantInputStyle,
  assistantToolbarStyle,
  clampAssistantHistoryWidth,
} from "../assistant-ui-config";

interface ConversationSidebarProps {
  conversations: Conversation[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onUpdate: (
    id: string,
    updates: { title?: string; pinned?: boolean },
  ) => Promise<void>;
  onReorder: (conversationIds: string[]) => Promise<void>;
  onDelete: (id: string) => void;
}

export function ConversationSidebar({
  conversations,
  activeId,
  onSelect,
  onNew,
  onUpdate,
  onReorder,
  onDelete,
}: ConversationSidebarProps) {
  const { t } = useTranslation();
  const [renameTarget, setRenameTarget] = useState<Conversation | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [isRenaming, setIsRenaming] = useState(false);
  const [isResizing, setIsResizing] = useState(false);
  const [draggedId, setDraggedId] = useState<string | null>(null);
  const [dropTargetId, setDropTargetId] = useState<string | null>(null);
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(() => new Set());
  const [isCollapsed, setIsCollapsed] = useState(
    () => window.localStorage.getItem(assistantHistoryPanel.collapsedStorageKey) === "true",
  );
  const [width, setWidth] = useState(() => {
    const stored = window.localStorage.getItem(assistantHistoryPanel.storageKey);
    return stored === null
      ? assistantHistoryPanel.defaultWidth
      : clampAssistantHistoryWidth(Number(stored));
  });
  const widthRef = useRef(width);
  const resizeStartRef = useRef<{ clientX: number; width: number } | null>(null);

  const applyWidth = (nextWidth: number, persist = false) => {
    const clampedWidth = clampAssistantHistoryWidth(nextWidth);
    widthRef.current = clampedWidth;
    setWidth(clampedWidth);
    if (persist) {
      window.localStorage.setItem(assistantHistoryPanel.storageKey, String(clampedWidth));
    }
  };

  const resizeFromPointer = (clientX: number, persist = false) => {
    const start = resizeStartRef.current;
    if (!start) return;
    applyWidth(start.width + clientX - start.clientX, persist);
  };

  const handlePointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    resizeStartRef.current = { clientX: event.clientX, width: widthRef.current };
    setIsResizing(true);
  };

  const handlePointerMove = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!resizeStartRef.current) return;
    event.preventDefault();
    resizeFromPointer(event.clientX);
  };

  const finishResize = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!resizeStartRef.current) return;
    resizeFromPointer(event.clientX, true);
    resizeStartRef.current = null;
    setIsResizing(false);
  };

  const cancelResize = () => {
    if (!resizeStartRef.current) return;
    window.localStorage.setItem(assistantHistoryPanel.storageKey, String(widthRef.current));
    resizeStartRef.current = null;
    setIsResizing(false);
  };

  const handleResizeKeyDown = (event: ReactKeyboardEvent<HTMLDivElement>) => {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    event.preventDefault();
    const direction = event.key === "ArrowLeft" ? -1 : 1;
    applyWidth(widthRef.current + direction * assistantHistoryPanel.keyboardStep, true);
  };

  const openRenameDialog = (conversation: Conversation) => {
    setRenameTarget(conversation);
    setRenameValue(conversation.title || t("assistant.newChat"));
  };

  const submitRename = async () => {
    const title = renameValue.trim();
    if (!renameTarget || !title || isRenaming) return;
    setIsRenaming(true);
    try {
      await onUpdate(renameTarget.id, { title });
      setRenameTarget(null);
    } finally {
      setIsRenaming(false);
    }
  };

  const canDropOn = (target: Conversation) => {
    const dragged = conversations.find((conversation) => conversation.id === draggedId);
    return dragged !== undefined
      && dragged.id !== target.id
      && Boolean(dragged.pinned_at) === Boolean(target.pinned_at);
  };

  const finishDrag = () => {
    setDraggedId(null);
    setDropTargetId(null);
  };

  const dropConversation = (target: Conversation) => {
    if (!draggedId || !canDropOn(target)) {
      finishDrag();
      return;
    }

    const next = [...conversations];
    const sourceIndex = next.findIndex((conversation) => conversation.id === draggedId);
    const targetIndex = next.findIndex((conversation) => conversation.id === target.id);
    const [dragged] = next.splice(sourceIndex, 1);
    next.splice(targetIndex, 0, dragged);
    finishDrag();
    void onReorder(next.map((conversation) => conversation.id));
  };

  const conversationGroups = [
    {
      key: "pinned",
      label: t("assistant.history.pinned"),
      items: conversations.filter((conversation) => conversation.pinned_at !== null),
    },
    {
      key: "chats",
      label: t("assistant.history.chats"),
      items: conversations.filter((conversation) => conversation.pinned_at === null),
    },
  ].filter((group) => group.items.length > 0);

  const toggleGroup = (groupKey: string) => {
    setCollapsedGroups((current) => {
      const next = new Set(current);
      if (next.has(groupKey)) next.delete(groupKey);
      else next.add(groupKey);
      return next;
    });
  };

  const setCollapsed = (collapsed: boolean) => {
    setIsCollapsed(collapsed);
    window.localStorage.setItem(
      assistantHistoryPanel.collapsedStorageKey,
      String(collapsed),
    );
  };

  return (
    <>
      <aside
        className={cn(
          "relative flex shrink-0 flex-col bg-background",
          !isResizing && "transition-[width] duration-200 ease-out motion-reduce:transition-none",
        )}
        style={{ width: isCollapsed ? assistantHistoryPanel.collapsedWidth : width }}
      >
        {isCollapsed ? (
          <div className="flex flex-col items-center gap-1 p-1.5">
            <TooltipIconButton
              label={t("assistant.history.expand")}
              tooltipSide="right"
              variant="ghost"
              size={assistantControlSizes.iconAction}
              style={assistantInputStyle}
              onClick={() => setCollapsed(false)}
            >
              <PanelLeftOpen className="size-[var(--icon-sm)]" />
            </TooltipIconButton>
            <TooltipIconButton
              label={t("assistant.newChat")}
              tooltipSide="right"
              variant="ghost"
              size={assistantControlSizes.iconAction}
              style={assistantInputStyle}
              onClick={onNew}
            >
              <Plus className="size-[var(--icon-sm)]" />
            </TooltipIconButton>
          </div>
        ) : (
          <>
        <div className="flex items-center justify-between gap-1 p-2">
          <TooltipIconButton
            label={t("assistant.newChat")}
            variant="outline"
            size={assistantControlSizes.iconAction}
            style={assistantInputStyle}
            onClick={onNew}
          >
            <Plus />
          </TooltipIconButton>
          <TooltipIconButton
            label={t("assistant.history.collapse")}
            variant="ghost"
            size={assistantControlSizes.iconAction}
            style={assistantInputStyle}
            onClick={() => setCollapsed(true)}
          >
            <PanelLeftClose className="size-[var(--icon-sm)]" />
          </TooltipIconButton>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-2">
          {conversations.length === 0 ? (
            <div className="px-2 py-6 text-center text-caption text-muted-foreground">
              {t("assistant.historyEmpty")}
            </div>
          ) : (
            conversationGroups.map((group) => (
              <section key={group.key} className="mb-2 last:mb-0">
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-7 w-full justify-start gap-1.5 px-2 py-1 font-medium text-muted-foreground hover:bg-transparent hover:text-foreground"
                  style={assistantToolbarStyle}
                  aria-expanded={!collapsedGroups.has(group.key)}
                  aria-controls={`assistant-history-${group.key}`}
                  onClick={() => toggleGroup(group.key)}
                >
                  {group.key === "pinned" ? (
                    <Pin className="size-[var(--icon-xs)]" />
                  ) : (
                    <MessageSquare className="size-[var(--icon-xs)]" />
                  )}
                  {group.label}
                  <ChevronDown
                    className={cn(
                      "ml-auto size-[var(--icon-xs)] transition-transform",
                      collapsedGroups.has(group.key) && "-rotate-90",
                    )}
                  />
                </Button>
                <div id={`assistant-history-${group.key}`}>
                {!collapsedGroups.has(group.key) && group.items.map((conversation) => (
              <div
                key={conversation.id}
                draggable
                className={cn(
                  "group flex cursor-grab items-center gap-2 rounded-md border border-transparent px-2 py-1.5 transition-[background-color,border-color,opacity,box-shadow] hover:border-border hover:bg-muted active:cursor-grabbing",
                  conversation.id === activeId && "bg-muted",
                  conversation.id === draggedId && "opacity-40",
                  conversation.id === dropTargetId && "ring-1 ring-ring",
                )}
                onClick={() => onSelect(conversation.id)}
                onDragStart={(event) => {
                  event.dataTransfer.effectAllowed = "move";
                  event.dataTransfer.setData("text/plain", conversation.id);
                  setDraggedId(conversation.id);
                }}
                onDragOver={(event) => {
                  if (!canDropOn(conversation)) return;
                  event.preventDefault();
                  event.dataTransfer.dropEffect = "move";
                  setDropTargetId(conversation.id);
                }}
                onDragLeave={() => {
                  if (dropTargetId === conversation.id) setDropTargetId(null);
                }}
                onDrop={(event) => {
                  event.preventDefault();
                  dropConversation(conversation);
                }}
                onDragEnd={finishDrag}
              >
                <span className="min-w-0 flex-1 truncate text-ui">
                  {conversation.title || t("assistant.newChat")}
                </span>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      variant="ghost"
                      size={assistantControlSizes.rowAction}
                      className="opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 data-[state=open]:opacity-100"
                      style={assistantInputStyle}
                      aria-label={t("assistant.history.more")}
                      title={t("assistant.history.more")}
                      onClick={(event) => event.stopPropagation()}
                    >
                      <MoreHorizontal className="size-[var(--icon-xs)]" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent
                    align="end"
                    className="w-36"
                    onClick={(event) => event.stopPropagation()}
                  >
                    <DropdownMenuItem
                      className="text-caption"
                      onSelect={() => void onUpdate(conversation.id, {
                        pinned: !conversation.pinned_at,
                      })}
                    >
                      {conversation.pinned_at ? <PinOff /> : <Pin />}
                      {t(conversation.pinned_at
                        ? "assistant.history.unpin"
                        : "assistant.history.pin")}
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      className="text-caption"
                      onSelect={() => openRenameDialog(conversation)}
                    >
                      <Pencil />
                      {t("assistant.history.rename")}
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      variant="destructive"
                      className="text-caption"
                      onSelect={() => onDelete(conversation.id)}
                    >
                      <Trash2 />
                      {t("assistant.history.delete")}
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
                ))}
                </div>
              </section>
            ))
          )}
        </div>
        <div
          role="separator"
          aria-label={t("assistant.history.resize")}
          aria-orientation="vertical"
          aria-valuemin={assistantHistoryPanel.minWidth}
          aria-valuemax={assistantHistoryPanel.maxWidth}
          aria-valuenow={width}
          tabIndex={0}
          className="group/resizer absolute inset-y-0 -right-1 z-20 flex w-2 touch-none cursor-col-resize justify-center outline-none"
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={finishResize}
          onPointerCancel={cancelResize}
          onKeyDown={handleResizeKeyDown}
        >
          <span
            className={cn(
              "h-full w-px bg-border transition-[background-color,box-shadow] duration-150 group-hover/resizer:bg-border-strong group-hover/resizer:shadow-[0_0_0_1px_var(--ring)] group-focus-visible/resizer:bg-border-strong group-focus-visible/resizer:shadow-[0_0_0_1px_var(--ring)]",
              isResizing && "bg-primary/60 shadow-[0_0_0_1px_var(--ring)]",
            )}
          />
        </div>
          </>
        )}
      </aside>

      <Dialog
        open={renameTarget !== null}
        onOpenChange={(open) => {
          if (!open && !isRenaming) setRenameTarget(null);
        }}
      >
        <DialogContent className="sm:max-w-md" showCloseButton={!isRenaming}>
          <DialogHeader>
            <DialogTitle className="text-subheading">
              {t("assistant.history.renameTitle")}
            </DialogTitle>
            <DialogDescription className="text-caption">
              {t("assistant.history.renameDescription")}
            </DialogDescription>
          </DialogHeader>
          <Input
            autoFocus
            value={renameValue}
            maxLength={100}
            placeholder={t("assistant.history.renamePlaceholder")}
            style={assistantInputStyle}
            disabled={isRenaming}
            onChange={(event) => setRenameValue(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                void submitRename();
              }
            }}
          />
          <DialogFooter>
            <Button
              variant="outline"
              size="sm"
              style={assistantInputStyle}
              disabled={isRenaming}
              onClick={() => setRenameTarget(null)}
            >
              {t("common.cancel")}
            </Button>
            <Button
              size="sm"
              style={assistantInputStyle}
              disabled={!renameValue.trim() || isRenaming}
              onClick={() => void submitRename()}
            >
              {t("assistant.history.renameSave")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
