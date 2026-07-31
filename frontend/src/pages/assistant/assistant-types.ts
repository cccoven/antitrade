import type {
  AgentWorkLog,
  AssistantInterruptItem,
  AssistantInterruptPreviewLine,
  ChatMessage,
} from "@/api/client";

export type { AgentWorkItem, AgentWorkLog, Conversation, ChatMessage } from "@/api/client";

export type InterruptPreviewLine = AssistantInterruptPreviewLine;
export type InterruptItem = AssistantInterruptItem;

export type StreamingMessage =
  | ChatMessage
  | {
      role: "interrupt";
      items: InterruptItem[];
      work?: AgentWorkLog;
      resolved?: "approved" | "rejected" | "expired";
    };
