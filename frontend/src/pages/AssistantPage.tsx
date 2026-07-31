import { useRef, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { useAuth } from "@/auth/auth-context";
import LoginRequiredPage from "@/auth/LoginRequiredPage";
import { useAssistant } from "./assistant/use-assistant";
import { ActionConfirmCard } from "./assistant/ActionConfirmCard";
import { AssistantComposer } from "./assistant/AssistantComposer";
import { ConversationSidebar } from "./assistant/ConversationSidebar";
import { MessageBubble } from "./assistant/MessageBubble";
import { AgentWorkLog } from "./assistant/AgentWorkLog";
import { ASSISTANT_COMMANDS } from "./assistant/command-registry";
import { assistantControlSizes, assistantInputStyle } from "./assistant-ui-config";
import type { AssistantRunOptions, UploadedAsset } from "@/api/client";
import { handleWindowDragDoubleClick, handleWindowDragMouseDown } from "@/lib/window-chrome";

export default function AssistantPage() {
  const { t } = useTranslation();
  const { user, loading: authLoading } = useAuth();
  const {
    conversations,
    activeId,
    messages,
    isStreaming,
    capabilities,
    selectConversation,
    newConversation,
    deleteConversation,
    updateConversation,
    reorderConversations,
    sendMessage,
    replaceLastMessage,
    resumeRun,
    stopStreaming,
  } = useAssistant();

  const [input, setInput] = useState("");
  const [attachments, setAttachments] = useState<UploadedAsset[]>([]);
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const shortcuts = ASSISTANT_COMMANDS.filter((item) => item.featured);

  const selectShortcut = (command: string) => {
    setInput(`${command} `);
    requestAnimationFrame(() => textareaRef.current?.focus());
  };

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages]);

  if (authLoading) return null;
  if (!user) {
    return (
      <div className="assistant-page flex h-full min-h-0 flex-col">
        <div
          className="assistant-window-drag-region"
          data-window-drag-region
          onMouseDown={handleWindowDragMouseDown}
          onDoubleClick={handleWindowDragDoubleClick}
        />
        <div className="min-h-0 flex-1"><LoginRequiredPage /></div>
      </div>
    );
  }

  const handleSend = (options: AssistantRunOptions) => {
    if ((!input.trim() && attachments.length === 0) || isStreaming) return;
    void sendMessage(input, options, attachments);
    setInput("");
    setAttachments([]);
  };

  let lastUserMessageIndex = -1;
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    if (messages[index].role === "user") {
      lastUserMessageIndex = index;
      break;
    }
  }

  return (
    <div className="assistant-page flex h-full min-h-0 flex-col">
      <div
        className="assistant-window-drag-region"
        data-window-drag-region
        onMouseDown={handleWindowDragMouseDown}
        onDoubleClick={handleWindowDragDoubleClick}
      />
      <div className="flex min-h-0 flex-1">
        <ConversationSidebar
          conversations={conversations}
          activeId={activeId}
          onSelect={(id) => {
            setAttachments([]);
            void selectConversation(id);
          }}
          onNew={() => {
            setAttachments([]);
            newConversation();
          }}
          onUpdate={updateConversation}
          onReorder={reorderConversations}
          onDelete={setDeleteTarget}
        />

        {/* Chat area */}
        <section className="flex min-w-0 flex-1 flex-col bg-card text-card-foreground">
        <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto flex max-w-3xl flex-col gap-4 px-4 py-6">
            {messages.length === 0 ? (
              <div className="flex flex-col items-center gap-3 py-16 text-center">
                <div className="title-description-stack items-center">
                  <div className="text-subheading font-medium">{t("assistant.emptyTitle")}</div>
                  <div className="text-caption text-muted-foreground">{t("assistant.emptyHint")}</div>
                </div>
                <div className="mt-3 grid w-full max-w-xl grid-cols-2 gap-2 sm:grid-cols-4">
                  {shortcuts.map(({ command, labelKey, icon: Icon }) => {
                    const capabilityKey = command.slice(1);
                    const marketCapability = capabilities.market_data?.[capabilityKey];
                    const unavailable = marketCapability?.configured === false;
                    return (
                      <Button
                        key={command}
                        variant="outline"
                        size={assistantControlSizes.primaryAction}
                        className="h-auto flex-col items-start gap-2 px-3 py-3"
                        style={assistantInputStyle}
                        disabled={unavailable}
                        title={unavailable ? t("assistant.market.commandUnavailable") : undefined}
                        onClick={() => selectShortcut(command)}
                      >
                        <Icon className="size-[var(--icon-sm)] text-primary" />
                        <span className="font-medium">{command}</span>
                        <span className="text-left text-caption font-normal text-muted-foreground">{t(labelKey)}</span>
                      </Button>
                    );
                  })}
                </div>
              </div>
            ) : (
              messages.map((msg, i) => {
                if (msg.role === "interrupt") {
                  return (
                    <div key={i} className="grid w-full gap-2">
                      {msg.work && <AgentWorkLog work={msg.work} />}
                      <ActionConfirmCard
                        items={msg.items}
                        resolved={msg.resolved}
                        onApprove={() => void resumeRun("approve")}
                        onReject={() => void resumeRun("reject")}
                      />
                    </div>
                  );
                }

                return (
                  <MessageBubble
                    key={msg.id}
                    message={msg}
                    canEdit={i === lastUserMessageIndex && !isStreaming}
                    onReplace={(content) => void replaceLastMessage(content)}
                  />
                );
              })
            )}
          </div>
        </div>

        <AssistantComposer
          input={input}
          isStreaming={isStreaming}
          capabilities={capabilities}
          attachments={attachments}
          textareaRef={textareaRef}
          onInputChange={setInput}
          onAttachmentsChange={setAttachments}
          onSend={handleSend}
          onStop={stopStreaming}
        />
        </section>
      </div>

      <ConfirmDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => { if (!open) setDeleteTarget(null); }}
        title={t("assistant.deleteTitle")}
        description={t("assistant.deleteBody")}
        onConfirm={() => {
          if (deleteTarget) void deleteConversation(deleteTarget);
          setDeleteTarget(null);
        }}
      />
    </div>
  );
}
