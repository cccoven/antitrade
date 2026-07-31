import { useState, useCallback, useRef, useEffect } from "react";
import i18n from "@/i18n";
import {
  listConversations,
  createConversation,
  updateConversation as apiUpdateConversation,
  reorderConversations as apiReorderConversations,
  getConversationMessages,
  getAssistantCapabilities,
  deleteConversation as apiDeleteConversation,
  assistantMessageUrl,
  assistantReplaceLastMessageUrl,
  assistantResumeUrl,
  type ChatMessage,
  type Conversation,
  type AgentWorkItem,
  type AgentWorkLog,
  type AssistantCapabilities,
  type AssistantArtifact,
  type AssistantRunOptions,
  type ConversationMessagePage,
  type UploadedAsset,
} from "@/api/client";
import type { InterruptItem, StreamingMessage } from "./assistant-types";
import { useBilling } from "@/billing/billing-context";

const ACTIVE_KEY = "antitrade.assistant.activeId";
const TOKEN_KEY = "antitrade.auth.token";
const DEFAULT_RUN_OPTIONS: AssistantRunOptions = { mode: "standard", webSearch: false };

type StreamOutcome = {
  kind: "done" | "interrupt" | "error" | "closed";
  errorCode?: string;
};

function localMessage(
  role: ChatMessage["role"], content: string, attachments?: UploadedAsset[],
): ChatMessage {
  return {
    id: `local-${Date.now()}-${Math.random().toString(36).slice(2)}`,
    role,
    content,
    attachments,
    created_at: new Date().toISOString(),
  };
}

function lastUserMessageIndex(items: StreamingMessage[]): number {
  for (let index = items.length - 1; index >= 0; index -= 1) {
    if (items[index].role === "user") return index;
  }
  return -1;
}

function updateLatestAssistant(
  items: StreamingMessage[],
  update: (message: ChatMessage) => ChatMessage,
): StreamingMessage[] {
  const updated = [...items];
  for (let index = updated.length - 1; index >= 0; index -= 1) {
    const message = updated[index];
    if (message.role === "assistant") {
      updated[index] = update(message);
      break;
    }
  }
  return updated;
}

function upsertWorkItem(work: AgentWorkLog | null | undefined, item: AgentWorkItem): AgentWorkLog {
  const current = work ?? {
    status: "running",
    started_at: new Date().toISOString(),
    duration_ms: 0,
    items: [],
  };
  const index = current.items.findIndex((entry) => entry.id === item.id);
  const items = [...current.items];
  if (index >= 0) items[index] = item;
  else items.push(item);
  return { ...current, status: "running", items };
}

function upsertArtifact(
  artifacts: AssistantArtifact[] | undefined,
  artifact: AssistantArtifact,
): AssistantArtifact[] {
  const items = [...(artifacts ?? [])];
  const index = items.findIndex((item) => item.id === artifact.id);
  if (index >= 0) items[index] = artifact;
  else items.push(artifact);
  return items;
}

function restoreMessages(page: ConversationMessagePage): StreamingMessage[] {
  if (!page.pending) return page.messages;
  return [
    ...page.messages,
    {
      role: "interrupt",
      items: page.pending.items,
      work: page.pending.work,
      resolved: page.pending.expired ? "expired" : undefined,
    },
  ];
}

async function loadConversationMessages(conversationId: string): Promise<StreamingMessage[]> {
  const first = await getConversationMessages(conversationId);
  let messages = first.messages;
  let nextOffset = first.page.next_offset;
  while (nextOffset !== null) {
    const older = await getConversationMessages(conversationId, first.page.limit, nextOffset);
    messages = [...older.messages, ...messages];
    nextOffset = older.page.next_offset;
  }
  return restoreMessages({ ...first, messages });
}

export function useAssistant() {
  const { refresh: refreshBilling } = useBilling();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(
    () => window.localStorage.getItem(ACTIVE_KEY),
  );
  const [messages, setMessages] = useState<StreamingMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [capabilities, setCapabilities] = useState<AssistantCapabilities>({
    web_search: { available: false, provider: null },
    vision: {
      available: false,
      max_images: 4,
      mime_types: ["image/png", "image/jpeg", "image/webp"],
    },
  });
  const abortRef = useRef<AbortController | null>(null);
  const lastRunOptionsRef = useRef<AssistantRunOptions>(DEFAULT_RUN_OPTIONS);

  const setActive = useCallback((id: string | null) => {
    setActiveId(id);
    if (id) window.localStorage.setItem(ACTIVE_KEY, id);
    else window.localStorage.removeItem(ACTIVE_KEY);
  }, []);

  const refreshConversations = useCallback(async () => {
    const list = await listConversations();
    setConversations(list);
    return list;
  }, []);

  // Initial load: fetch list, resolve active conversation + its messages.
  useEffect(() => {
    void (async () => {
      const [list, capabilityResult] = await Promise.all([
        refreshConversations(),
        getAssistantCapabilities().catch(() => null),
      ]);
      if (capabilityResult) setCapabilities(capabilityResult);
      const stored = window.localStorage.getItem(ACTIVE_KEY);
      const chosen = list.find((c) => c.id === stored) ?? list[0] ?? null;
      setActive(chosen ? chosen.id : null);
      setMessages(chosen ? await loadConversationMessages(chosen.id) : []);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const selectConversation = useCallback(async (id: string) => {
    lastRunOptionsRef.current = DEFAULT_RUN_OPTIONS;
    setActive(id);
    setMessages(await loadConversationMessages(id));
  }, [setActive]);

  const newConversation = useCallback(() => {
    abortRef.current?.abort();
    lastRunOptionsRef.current = DEFAULT_RUN_OPTIONS;
    setActive(null);
    setMessages([]);
  }, [setActive]);

  const deleteConversation = useCallback(async (id: string) => {
    await apiDeleteConversation(id);
    const list = await refreshConversations();
    if (activeId === id) {
      const next = list[0] ?? null;
      lastRunOptionsRef.current = DEFAULT_RUN_OPTIONS;
      setActive(next ? next.id : null);
      setMessages(next ? await loadConversationMessages(next.id) : []);
    }
  }, [activeId, refreshConversations, setActive]);

  const updateConversation = useCallback(async (
    id: string,
    updates: { title?: string; pinned?: boolean },
  ) => {
    await apiUpdateConversation(id, updates);
    await refreshConversations();
  }, [refreshConversations]);

  const reorderConversations = useCallback(async (conversationIds: string[]) => {
    const previous = conversations;
    const byId = new Map(previous.map((conversation) => [conversation.id, conversation]));
    if (conversationIds.length !== previous.length || conversationIds.some((id) => !byId.has(id))) {
      return;
    }

    setConversations(conversationIds.map((id) => byId.get(id)!));
    try {
      setConversations(await apiReorderConversations(conversationIds));
    } catch {
      setConversations(previous);
    }
  }, [conversations]);

  const consumeStream = useCallback(async (response: Response): Promise<StreamOutcome> => {
    if (response.status === 402) {
      const payload = await response.json().catch(() => null) as {
        data?: { feature?: string; reason?: string };
      } | null;
      window.dispatchEvent(new CustomEvent("billing:upgrade-required", {
        detail: payload?.data ?? {},
      }));
      return { kind: "error", errorCode: payload?.data?.reason ?? "billing_required" };
    }
    if (!response.ok || !response.body) throw new Error(`HTTP ${response.status}`);

    setMessages((prev) => [...prev, localMessage("assistant", "")]);
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let done = false;
    let outcome: StreamOutcome = { kind: "closed" };

    while (!done) {
      const { done: streamDone, value } = await reader.read();
      if (streamDone) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        let data: {
          type?: string;
          content?: string;
          items?: InterruptItem[];
          item?: AgentWorkItem;
          artifact?: AssistantArtifact;
          work?: AgentWorkLog;
          code?: string;
        };
        try {
          data = JSON.parse(line.slice(6));
        } catch {
          continue;
        }

        if (data.type === "delta") {
          setMessages((prev) => updateLatestAssistant(prev, (message) => ({
            ...message,
            content: message.content + (data.content || ""),
          })));
        } else if (data.type === "work_start" && data.work) {
          setMessages((prev) => updateLatestAssistant(prev, (message) => ({
            ...message,
            work: data.work,
          })));
        } else if (data.type === "work_item" && data.item) {
          setMessages((prev) => updateLatestAssistant(prev, (message) => ({
            ...message,
            work: upsertWorkItem(message.work, data.item!),
          })));
        } else if (data.type === "artifact" && data.artifact) {
          setMessages((prev) => updateLatestAssistant(prev, (message) => ({
            ...message,
            artifacts: upsertArtifact(message.artifacts, data.artifact!),
          })));
        } else if (data.type === "work_end" && data.work) {
          setMessages((prev) => updateLatestAssistant(prev, (message) => ({
            ...message,
            work: data.work,
          })));
        } else if (data.type === "interrupt") {
          setMessages((prev) => {
            const updated = [...prev];
            const last = updated[updated.length - 1];
            let work: AgentWorkLog | undefined;
            if (last?.role === "assistant") {
              work = last.work ?? undefined;
              if (last.content === "") updated.pop();
              else updated[updated.length - 1] = { ...last, work: undefined };
            }
            updated.push({ role: "interrupt", items: data.items || [], work });
            return updated;
          });
          outcome = { kind: "interrupt" };
          done = true;
          break;
        } else if (data.type === "error") {
          setMessages((prev) => {
            const updated = [...prev];
            const last = updated[updated.length - 1];
            const content = data.content || `**${i18n.t("assistant.error")}**`;
            if (last?.role === "assistant") {
              updated[updated.length - 1] = {
                ...last,
                content,
                work: last.work ? {
                  ...last.work,
                  status: "error",
                  completed_at: new Date().toISOString(),
                } : last.work,
              };
            } else {
              updated.push(localMessage("assistant", content));
            }
            return updated;
          });
          outcome = { kind: "error", errorCode: data.code };
          done = true;
          break;
        } else if (data.type === "done") {
          setMessages((prev) => updateLatestAssistant(prev, (message) => (
            message.work?.status === "running"
              ? {
                  ...message,
                  work: {
                    ...message.work,
                    status: "completed",
                    completed_at: new Date().toISOString(),
                  },
                }
              : message
          )));
          outcome = { kind: "done" };
          done = true;
          break;
        }
      }
    }
    return outcome;
  }, []);

  const runMessageRequest = useCallback(async (
    url: string,
    method: "POST" | "PUT",
    content: string,
    options: AssistantRunOptions,
    attachmentIds?: string[],
  ) => {
    setIsStreaming(true);
    const abort = new AbortController();
    abortRef.current = abort;

    try {
      const token = window.localStorage.getItem(TOKEN_KEY);
      const response = await fetch(url, {
        method,
        headers: {
          "Content-Type": "application/json",
          "Accept-Language": i18n.language,
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          content,
          mode: options.mode,
          web_search: options.webSearch && capabilities.web_search.available,
          ...(attachmentIds !== undefined ? { attachment_ids: attachmentIds } : {}),
        }),
        signal: abort.signal,
      });
      await consumeStream(response);
    } catch (err) {
      if ((err as Error).name === "AbortError") {
        setMessages((prev) => {
          const updated = updateLatestAssistant(prev, (message) => ({
            ...message,
            work: message.work ? {
              ...message.work,
              status: "error",
              completed_at: new Date().toISOString(),
            } : message.work,
          }));
          const last = updated[updated.length - 1];
          if (last?.role === "assistant" && !last.content && !last.work) updated.pop();
          return updated;
        });
      } else {
        setMessages((prev) => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          const errorContent = `**${i18n.t("assistant.error")}**`;
          if (last?.role === "assistant" && last.content === "") {
            updated[updated.length - 1] = { ...last, content: errorContent };
          } else {
            updated.push(localMessage("assistant", errorContent));
          }
          return updated;
        });
      }
    } finally {
      setIsStreaming(false);
      abortRef.current = null;
      void refreshConversations();
      void refreshBilling();
    }
  }, [capabilities.web_search.available, consumeStream, refreshBilling, refreshConversations]);

  const sendMessage = useCallback(async (
    content: string,
    options: AssistantRunOptions = DEFAULT_RUN_OPTIONS,
    attachments: UploadedAsset[] = [],
  ) => {
    const text = content.trim() || i18n.t("assistant.vision.defaultPrompt");
    if ((!content.trim() && attachments.length === 0) || isStreaming) return;

    // Ensure there is an active conversation.
    let convId = activeId;
    if (!convId) {
      const conv = await createConversation();
      convId = conv.id;
      setActive(convId);
      await refreshConversations();
    }

    setMessages((prev) => prev.map((msg) => (
      msg.role === "interrupt" && !msg.resolved
        ? { ...msg, resolved: "expired" }
        : msg
    )));
    setMessages((prev) => [...prev, localMessage("user", text, attachments)]);
    lastRunOptionsRef.current = options;
    await runMessageRequest(
      assistantMessageUrl(convId), "POST", text, options,
      attachments.map((attachment) => attachment.id),
    );
  }, [activeId, isStreaming, refreshConversations, runMessageRequest, setActive]);

  const replaceLastMessage = useCallback(async (content: string) => {
    const text = content.trim();
    if (!text || !activeId || isStreaming) return;
    if (lastUserMessageIndex(messages) < 0) return;

    setMessages((prev) => {
      const index = lastUserMessageIndex(prev);
      if (index < 0) return prev;
      const previous = prev[index];
      return [
        ...prev.slice(0, index),
        localMessage(
          "user",
          text,
          previous.role === "user" ? previous.attachments : undefined,
        ),
      ];
    });
    const options = lastRunOptionsRef.current;
    await runMessageRequest(
      assistantReplaceLastMessageUrl(activeId),
      "PUT",
      text,
      options,
    );
  }, [activeId, isStreaming, messages, runMessageRequest]);

  const resumeRun = useCallback(async (decision: "approve" | "reject") => {
    if (!activeId || isStreaming) return;

    const target = [...messages].reverse().find(
      (message) => message.role === "interrupt" && !message.resolved,
    );
    const callIds = target?.role === "interrupt"
      ? target.items.map((item) => item.call_id)
      : [];
    if (callIds.length === 0) return;

    setIsStreaming(true);
    const abort = new AbortController();
    abortRef.current = abort;

    try {
      const token = window.localStorage.getItem(TOKEN_KEY);
      const response = await fetch(assistantResumeUrl(activeId), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Accept-Language": i18n.language,
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          decisions: callIds.map((call_id) => ({ call_id, decision })),
        }),
        signal: abort.signal,
      });
      const outcome = await consumeStream(response);
      const staleCodes = new Set([
        "no_pending_approval", "pending_expired", "pending_already_consumed",
      ]);
      if (outcome.kind !== "error" && outcome.kind !== "closed") {
        setMessages((prev) => prev.map((message) => (
          message.role === "interrupt"
          && !message.resolved
          && message.items.some((item) => callIds.includes(item.call_id))
            ? {
                ...message,
                resolved: decision === "approve" ? "approved" as const : "rejected" as const,
                work: undefined,
              }
            : message
        )));
      } else if (outcome.errorCode && staleCodes.has(outcome.errorCode)) {
        setMessages((prev) => prev.map((message) => (
          message.role === "interrupt"
          && !message.resolved
          && message.items.some((item) => callIds.includes(item.call_id))
            ? { ...message, resolved: "expired" as const }
            : message
        )));
      }
    } catch (err) {
      if ((err as Error).name === "AbortError") {
        setMessages((prev) => updateLatestAssistant(prev, (message) => ({
          ...message,
          work: message.work ? {
            ...message.work,
            status: "error",
            completed_at: new Date().toISOString(),
          } : message.work,
        })));
      } else {
        setMessages((prev) => [
          ...prev,
          localMessage("assistant", `**${i18n.t("assistant.error")}**`),
        ]);
      }
    } finally {
      setIsStreaming(false);
      abortRef.current = null;
      void refreshConversations();
    }
  }, [activeId, consumeStream, isStreaming, messages, refreshConversations]);

  const stopStreaming = useCallback(() => abortRef.current?.abort(), []);

  return {
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
  };
}
