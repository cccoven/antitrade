import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type ClipboardEvent,
  type DragEvent,
  type KeyboardEvent,
  type RefObject,
} from "react";
import { useTranslation } from "react-i18next";
import {
  Crown, Globe2, ImagePlus, LoaderCircle, RotateCcw, SendHorizonal, Sparkles, Square, X,
} from "lucide-react";
import {
  authedAssetUrl,
  optimizeAssistantPrompt,
  uploadAsset,
  type AssistantAgentMode,
  type AssistantCapabilities,
  type AssistantRunOptions,
  type UploadedAsset,
} from "@/api/client";
import { Button } from "@/components/ui/button";
import ImagePreviewDialog from "@/components/ImagePreviewDialog";
import { showToast } from "@/components/Toast";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import {
  assistantControlSizes,
  assistantInputStyle,
  assistantToolbarStyle,
} from "../assistant-ui-config";
import {
  parseAssistantCommandInput,
  resolveAssistantCommands,
  serializeAssistantCommandInput,
  type ResolvedAssistantCommand,
} from "./command-registry";
import { SlashCommandMenu } from "./SlashCommandMenu";
import { useBilling } from "@/billing/billing-context";

const AGENT_MODE_COLOR_CLASSES: Record<AssistantAgentMode, string> = {
  quick: "text-agent-quick",
  standard: "text-agent-standard",
  research: "text-agent-research",
};

interface AssistantComposerProps {
  input: string;
  isStreaming: boolean;
  capabilities: AssistantCapabilities;
  attachments: UploadedAsset[];
  textareaRef: RefObject<HTMLTextAreaElement | null>;
  onInputChange: (value: string) => void;
  onAttachmentsChange: (attachments: UploadedAsset[]) => void;
  onSend: (options: AssistantRunOptions) => void;
  onStop: () => void;
}

const MAX_ATTACHMENT_BYTES = 8 * 1024 * 1024;
const MAX_TOTAL_ATTACHMENT_BYTES = 16 * 1024 * 1024;

function slashQuery(value: string): string | null {
  const match = value.match(/(?:^|\s)\/([^\s/]*)$/);
  return match ? match[1] : null;
}

function removeSlashQuery(value: string): string {
  return value.replace(/(?:^|\s)\/[^\s/]*$/, "").trimEnd();
}

export function AssistantComposer({
  input,
  isStreaming,
  capabilities,
  attachments,
  textareaRef,
  onInputChange,
  onAttachmentsChange,
  onSend,
  onStop,
}: AssistantComposerProps) {
  const { t } = useTranslation();
  const { canUse, openUpgrade, refresh: refreshBilling } = useBilling();
  const [mode, setMode] = useState<AssistantAgentMode>("standard");
  const [webSearch, setWebSearch] = useState(false);
  const [slashDismissed, setSlashDismissed] = useState(false);
  const [selectedCommandIndex, setSelectedCommandIndex] = useState(0);
  const [isOptimizing, setIsOptimizing] = useState(false);
  const [optimizedPreview, setOptimizedPreview] = useState<string | null>(null);
  const [undoValue, setUndoValue] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [preview, setPreview] = useState<UploadedAsset | null>(null);
  const originalForPreview = useRef("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const parsedInput = useMemo(
    () => parseAssistantCommandInput(input, capabilities.commands),
    [capabilities.commands, input],
  );
  const query = slashQuery(parsedInput.text);
  const matchingCommands = useMemo(
    () => resolveAssistantCommands(query ?? "", t, capabilities.commands),
    [capabilities.commands, query, t],
  );
  const availableCommands = useMemo(
    () => resolveAssistantCommands("", t, capabilities.commands),
    [capabilities.commands, t],
  );
  const commandTokens = parsedInput.commands
    .map((command) => availableCommands.find((item) => item.command === command))
    .filter((item): item is ResolvedAssistantCommand => item !== undefined);
  const showCommands = query !== null && !slashDismissed && !isStreaming;

  useEffect(() => {
    setSelectedCommandIndex(0);
  }, [query]);

  useEffect(() => {
    if (!capabilities.web_search.available) setWebSearch(false);
  }, [capabilities.web_search.available]);

  const updateInputText = (value: string) => {
    onInputChange(serializeAssistantCommandInput(parsedInput.commands, value));
    setSlashDismissed(false);
    setOptimizedPreview(null);
    setUndoValue(null);
  };

  const selectCommand = (item: ResolvedAssistantCommand) => {
    const nextCommands = parsedInput.commands.includes(item.command)
      ? parsedInput.commands
      : [...parsedInput.commands, item.command];
    onInputChange(serializeAssistantCommandInput(
      nextCommands,
      removeSlashQuery(parsedInput.text),
    ));
    setSlashDismissed(true);
    requestAnimationFrame(() => textareaRef.current?.focus());
  };

  const removeCommand = (command: string) => {
    onInputChange(serializeAssistantCommandInput(
      parsedInput.commands.filter((item) => item !== command),
      parsedInput.text,
    ));
    setOptimizedPreview(null);
    setUndoValue(null);
    requestAnimationFrame(() => textareaRef.current?.focus());
  };

  const submit = () => {
    if ((!input.trim() && attachments.length === 0) || isStreaming || isUploading) return;
    if (mode === "research" && !canUse("assistant.research")) {
      openUpgrade("assistant.research");
      return;
    }
    if (webSearch && !canUse("assistant.web_search")) {
      openUpgrade("assistant.web_search");
      return;
    }
    if (attachments.length > 0 && !canUse("assistant.vision")) {
      openUpgrade("assistant.vision");
      return;
    }
    setOptimizedPreview(null);
    setUndoValue(null);
    onSend({ mode, webSearch });
  };

  const addFiles = async (files: File[]) => {
    if (!capabilities.vision.available || isUploading || files.length === 0) return;
    if (!canUse("assistant.vision")) {
      openUpgrade("assistant.vision");
      return;
    }
    const acceptedTypes = new Set(capabilities.vision.mime_types);
    const validFiles = files.filter((file) => acceptedTypes.has(file.type));
    if (validFiles.length !== files.length) {
      showToast(t("assistant.vision.unsupportedType"));
    }

    const availableSlots = Math.max(
      0, capabilities.vision.max_images - attachments.length,
    );
    if (validFiles.length > availableSlots) {
      showToast(t("assistant.vision.tooMany", { count: capabilities.vision.max_images }));
    }

    let totalBytes = attachments.reduce((total, item) => total + item.size_bytes, 0);
    const candidates: File[] = [];
    for (const file of validFiles.slice(0, availableSlots)) {
      if (
        file.size > MAX_ATTACHMENT_BYTES
        || totalBytes + file.size > MAX_TOTAL_ATTACHMENT_BYTES
      ) {
        showToast(t("assistant.vision.tooLarge"));
        continue;
      }
      candidates.push(file);
      totalBytes += file.size;
    }
    if (candidates.length === 0) return;

    setIsUploading(true);
    const uploaded: UploadedAsset[] = [];
    try {
      for (const file of candidates) {
        uploaded.push(await uploadAsset(file));
      }
    } catch (error) {
      showToast(error instanceof Error ? error.message : t("error.generic"));
    } finally {
      if (uploaded.length > 0) onAttachmentsChange([...attachments, ...uploaded]);
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handlePaste = (event: ClipboardEvent<HTMLTextAreaElement>) => {
    const files = Array.from(event.clipboardData.files);
    if (files.length === 0) return;
    event.preventDefault();
    void addFiles(files);
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragging(false);
    void addFiles(Array.from(event.dataTransfer.files));
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (showCommands && matchingCommands.length > 0) {
      if (event.key === "ArrowDown") {
        event.preventDefault();
        setSelectedCommandIndex((index) => (index + 1) % matchingCommands.length);
        return;
      }
      if (event.key === "ArrowUp") {
        event.preventDefault();
        setSelectedCommandIndex(
          (index) => (index - 1 + matchingCommands.length) % matchingCommands.length,
        );
        return;
      }
      if (event.key === "Enter" || event.key === "Tab") {
        event.preventDefault();
        selectCommand(
          matchingCommands[selectedCommandIndex] ?? matchingCommands[0],
        );
        return;
      }
    }
    if (event.key === "Escape" && showCommands) {
      event.preventDefault();
      setSlashDismissed(true);
      return;
    }
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      submit();
    }
  };

  const optimize = async () => {
    if (input.trim().length < 3 || isOptimizing) return;
    originalForPreview.current = input;
    setIsOptimizing(true);
    try {
      const optimized = await optimizeAssistantPrompt(input);
      setOptimizedPreview(optimized);
    } finally {
      setIsOptimizing(false);
      void refreshBilling();
    }
  };

  const acceptOptimization = () => {
    if (!optimizedPreview) return;
    setUndoValue(originalForPreview.current);
    onInputChange(optimizedPreview);
    setOptimizedPreview(null);
    requestAnimationFrame(() => textareaRef.current?.focus());
  };

  const restoreOriginal = () => {
    if (undoValue === null) return;
    onInputChange(undoValue);
    setUndoValue(null);
    requestAnimationFrame(() => textareaRef.current?.focus());
  };

  return (
    <div className="p-3">
      <div className="relative mx-auto max-w-3xl">
        {showCommands && (
          <div className="absolute right-0 bottom-full left-0 z-40 mb-2">
            <SlashCommandMenu
              commands={matchingCommands}
              selectedIndex={selectedCommandIndex}
              onSelect={selectCommand}
            />
          </div>
        )}

        <div
          className={cn(
            "overflow-hidden rounded-[var(--radius-xl)] border border-border bg-card shadow-[var(--shadow-md)] transition-colors",
            isDragging && capabilities.vision.available && "border-primary bg-primary/5",
          )}
          onDragEnter={(event) => {
            event.preventDefault();
            if (capabilities.vision.available) setIsDragging(true);
          }}
          onDragOver={(event) => event.preventDefault()}
          onDragLeave={(event) => {
            if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
              setIsDragging(false);
            }
          }}
          onDrop={handleDrop}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept={capabilities.vision.mime_types.join(",")}
            multiple
            className="hidden"
            onChange={(event) => void addFiles(Array.from(event.target.files ?? []))}
          />
          {attachments.length > 0 && (
            <div className="flex gap-2 overflow-x-auto border-b border-border px-3 py-2.5">
              {attachments.map((attachment) => (
                <div
                  key={attachment.id}
                  className="group/attachment relative h-14 w-24 shrink-0 overflow-hidden rounded-md border border-border bg-muted"
                >
                  <button
                    type="button"
                    className="h-full w-full"
                    onClick={() => setPreview(attachment)}
                    aria-label={t("assistant.vision.preview")}
                  >
                    <img
                      src={authedAssetUrl(attachment.url)}
                      alt={attachment.original_name ?? t("assistant.vision.image")}
                      className="h-full w-full object-cover"
                    />
                  </button>
                  <Button
                    type="button"
                    variant="destructive"
                    size="icon-xs"
                    className="absolute right-1 top-1 opacity-0 transition-opacity group-hover/attachment:opacity-100"
                    style={assistantToolbarStyle}
                    disabled={isStreaming || isUploading}
                    onClick={() => onAttachmentsChange(
                      attachments.filter((item) => item.id !== attachment.id),
                    )}
                    aria-label={t("assistant.vision.remove")}
                    title={t("assistant.vision.remove")}
                  >
                    <X />
                  </Button>
                </div>
              ))}
            </div>
          )}
          {optimizedPreview && (
            <div className="border-b border-border bg-muted/40 px-3 py-2.5">
              <div className="mb-1 text-caption font-medium text-foreground">
                {t("assistant.optimize.preview")}
              </div>
              <div className="max-h-28 overflow-y-auto whitespace-pre-wrap text-ui text-muted-foreground">
                {optimizedPreview}
              </div>
              <div className="mt-2 flex justify-end gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  style={assistantInputStyle}
                  onClick={() => setOptimizedPreview(null)}
                >
                  {t("assistant.optimize.keepOriginal")}
                </Button>
                <Button
                  size="sm"
                  style={assistantInputStyle}
                  onClick={acceptOptimization}
                >
                  {t("assistant.optimize.replace")}
                </Button>
              </div>
            </div>
          )}

          <div className="flex min-h-[76px] flex-wrap content-start items-start gap-1.5 px-4 py-4">
            {commandTokens.map(({ command, label, icon: Icon }) => (
              <Button
                key={command}
                variant="ghost"
                size="sm"
                className="group/token h-7 shrink-0 gap-1.5 rounded-md bg-primary/10 px-2 text-primary hover:bg-primary/15 hover:text-primary"
                style={assistantToolbarStyle}
                disabled={isStreaming}
                aria-label={t("assistant.command.remove", { command: label })}
                title={t("assistant.command.remove", { command: label })}
                onClick={() => removeCommand(command)}
              >
                <Icon className="size-[var(--icon-xs)]" />
                <span className="font-medium">{label}</span>
                <X className="size-[var(--icon-xs)] opacity-50 transition-opacity group-hover/token:opacity-100" />
              </Button>
            ))}
            <Textarea
              ref={textareaRef}
              value={parsedInput.text}
              onChange={(event) => updateInputText(event.target.value)}
              onKeyDown={handleKeyDown}
              onPaste={handlePaste}
              placeholder={t("assistant.inputPlaceholderRich")}
              className={cn(
                "max-h-[148px] min-h-11 min-w-[180px] flex-[1_1_240px] resize-none rounded-none border-0 bg-transparent px-0 pb-0 pt-1 text-ui shadow-none focus-visible:border-transparent focus-visible:ring-0",
                commandTokens.length === 0 && "basis-full",
              )}
              style={assistantInputStyle}
              rows={2}
            />
          </div>

          <div className="flex min-h-11 items-center justify-between gap-2 px-3 py-2.5">
            <div className="flex min-w-0 items-center gap-1">
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <span>
                      <Button
                        type="button"
                        variant="ghost"
                        size={assistantControlSizes.iconAction}
                        style={assistantToolbarStyle}
                        disabled={
                          !capabilities.vision.available
                          || attachments.length >= capabilities.vision.max_images
                          || isStreaming
                          || isUploading
                        }
                        onClick={() => {
                          if (!canUse("assistant.vision")) {
                            openUpgrade("assistant.vision");
                            return;
                          }
                          fileInputRef.current?.click();
                        }}
                        aria-label={t("assistant.vision.add")}
                      >
                        {isUploading ? (
                          <LoaderCircle className="size-[var(--icon-sm)] animate-spin" />
                        ) : (
                          <ImagePlus className="size-[var(--icon-sm)]" />
                        )}
                      </Button>
                    </span>
                  </TooltipTrigger>
                  <TooltipContent>
                    {capabilities.vision.available
                      ? canUse("assistant.vision")
                        ? t("assistant.vision.addHint")
                        : t("billing.proFeature")
                      : t("assistant.vision.unavailable")}
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
              <Button
                variant="ghost"
                size="sm"
                className="font-normal"
                style={assistantToolbarStyle}
                onClick={() => void optimize()}
                disabled={input.trim().length < 3 || isOptimizing || isStreaming}
              >
                <Sparkles className="size-[var(--icon-xs)]" />
                {isOptimizing ? t("assistant.optimize.loading") : t("assistant.optimize.action")}
              </Button>
              {undoValue !== null && (
                <Button
                  variant="ghost"
                  size="sm"
                  style={assistantToolbarStyle}
                  onClick={restoreOriginal}
                >
                  <RotateCcw className="size-[var(--icon-xs)]" />
                  {t("assistant.optimize.undo")}
                </Button>
              )}
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <span>
                      <Button
                        variant="ghost"
                        size="sm"
                        className={cn("font-normal", webSearch && "bg-primary/10 text-primary")}
                        style={assistantToolbarStyle}
                        aria-pressed={webSearch}
                        disabled={!capabilities.web_search.available || isStreaming}
                        onClick={() => {
                          if (!canUse("assistant.web_search")) {
                            openUpgrade("assistant.web_search");
                            return;
                          }
                          setWebSearch((enabled) => !enabled);
                        }}
                      >
                        <Globe2 className="size-[var(--icon-xs)]" />
                        {t("assistant.webSearch")}
                      </Button>
                    </span>
                  </TooltipTrigger>
                  <TooltipContent>
                    {!capabilities.web_search.available
                      ? t("assistant.webSearchUnavailable")
                      : canUse("assistant.web_search")
                        ? t("assistant.webSearch")
                        : t("billing.proFeature")}
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>

            <div className="flex shrink-0 items-center gap-1.5">
              <Select
                value={mode}
                onValueChange={(value) => {
                  const next = value as AssistantAgentMode;
                  if (next === "research" && !canUse("assistant.research")) {
                    openUpgrade("assistant.research");
                    return;
                  }
                  setMode(next);
                }}
                disabled={isStreaming}
              >
                <SelectTrigger
                  size="sm"
                  className={cn(
                    "gap-1.5 border-0 bg-transparent px-2 font-normal",
                    AGENT_MODE_COLOR_CLASSES[mode],
                  )}
                  style={assistantToolbarStyle}
                >
                  <SelectValue>{t(`assistant.agent.${mode}`)}</SelectValue>
                </SelectTrigger>
                <SelectContent align="end" className="w-[230px]">
                  {(["quick", "standard", "research"] as AssistantAgentMode[]).map((item) => (
                    <SelectItem key={item} value={item}>
                      <span className="flex flex-col items-start">
                        <span className={cn(
                          "flex items-center gap-1 text-caption leading-4",
                          AGENT_MODE_COLOR_CLASSES[item],
                        )}>
                          {t(`assistant.agent.${item}`)}
                          {item === "research" && !canUse("assistant.research")
                            ? <Crown className="size-[var(--icon-xs)]" />
                            : null}
                        </span>
                        <span className="text-micro leading-4 text-muted-foreground">
                          {t(`assistant.agent.${item}.description`)}
                        </span>
                      </span>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {isStreaming ? (
                <Button
                  variant="outline"
                  size={assistantControlSizes.iconAction}
                  className="rounded-full"
                  style={assistantToolbarStyle}
                  onClick={onStop}
                  aria-label={t("assistant.stop")}
                >
                  <Square className="size-[var(--icon-sm)]" />
                </Button>
              ) : (
                <Button
                  size={assistantControlSizes.iconAction}
                  className="rounded-full"
                  style={assistantToolbarStyle}
                  onClick={submit}
                  disabled={
                    (!input.trim() && attachments.length === 0) || isUploading
                  }
                  aria-label={t("assistant.send")}
                >
                  <SendHorizonal className="size-[var(--icon-sm)]" />
                </Button>
              )}
            </div>
          </div>
        </div>
      </div>
      <ImagePreviewDialog
        image={preview}
        open={preview !== null}
        onOpenChange={(open) => !open && setPreview(null)}
      />
    </div>
  );
}
