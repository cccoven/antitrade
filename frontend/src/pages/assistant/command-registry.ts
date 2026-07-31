import type { TFunction } from "i18next";
import type { LucideIcon } from "lucide-react";
import {
  Bitcoin,
  BookOpenText,
  ChartCandlestick,
  CircleHelp,
  Globe2,
  Gauge,
  Landmark,
  LineChart,
  Newspaper,
  NotebookText,
  PieChart,
  ShieldCheck,
  Sparkles,
} from "lucide-react";

export type AssistantCommandGroup = "market" | "personal" | "assistant";

export interface AssistantCommand {
  command: string;
  labelKey: string;
  descriptionKey: string;
  group: AssistantCommandGroup;
  icon: LucideIcon;
  featured?: boolean;
}

export interface ResolvedAssistantCommand extends AssistantCommand {
  label: string;
  description: string;
  groupLabel: string;
}

export interface ParsedAssistantCommandInput {
  commands: string[];
  text: string;
}

export const ASSISTANT_COMMANDS: AssistantCommand[] = [
  { command: "/stock", labelKey: "assistant.shortcut.stock", descriptionKey: "assistant.command.stock.description", group: "market", icon: ChartCandlestick, featured: true },
  { command: "/forex", labelKey: "assistant.shortcut.forex", descriptionKey: "assistant.command.forex.description", group: "market", icon: Globe2, featured: true },
  { command: "/crypto", labelKey: "assistant.shortcut.crypto", descriptionKey: "assistant.command.crypto.description", group: "market", icon: Bitcoin, featured: true },
  { command: "/futures", labelKey: "assistant.command.futures", descriptionKey: "assistant.command.futures.description", group: "market", icon: Gauge },
  { command: "/check", labelKey: "assistant.command.check", descriptionKey: "assistant.command.check.description", group: "personal", icon: ShieldCheck },
  { command: "/macro", labelKey: "assistant.shortcut.macro", descriptionKey: "assistant.command.macro.description", group: "market", icon: Landmark, featured: true },
  { command: "/news", labelKey: "assistant.command.news", descriptionKey: "assistant.command.news.description", group: "market", icon: Newspaper },
  { command: "/journal", labelKey: "assistant.command.journal", descriptionKey: "assistant.command.journal.description", group: "personal", icon: NotebookText },
  { command: "/portfolio", labelKey: "assistant.command.portfolio", descriptionKey: "assistant.command.portfolio.description", group: "personal", icon: PieChart },
  { command: "/strategy", labelKey: "assistant.command.strategy", descriptionKey: "assistant.command.strategy.description", group: "personal", icon: LineChart },
  { command: "/review", labelKey: "assistant.command.review", descriptionKey: "assistant.command.review.description", group: "personal", icon: BookOpenText },
  { command: "/remember", labelKey: "assistant.command.remember", descriptionKey: "assistant.command.remember.description", group: "assistant", icon: Sparkles },
  { command: "/help", labelKey: "assistant.command.help", descriptionKey: "assistant.command.help.description", group: "assistant", icon: CircleHelp },
];

export function resolveAssistantCommands(
  query: string,
  t: TFunction,
  availableCommands?: readonly string[],
): ResolvedAssistantCommand[] {
  const normalized = query.trim().toLowerCase();
  const available = availableCommands ? new Set(availableCommands) : null;
  return ASSISTANT_COMMANDS.map((item) => ({
    ...item,
    label: t(item.labelKey),
    description: t(item.descriptionKey),
    groupLabel: t(`assistant.command.group.${item.group}`),
  })).filter((item) => (
    (!available || available.has(item.command))
    && (
      !normalized
      || item.command.slice(1).includes(normalized)
      || item.label.toLowerCase().includes(normalized)
      || item.description.toLowerCase().includes(normalized)
    )
  ));
}

export function parseAssistantCommandInput(
  value: string,
  availableCommands?: readonly string[],
): ParsedAssistantCommandInput {
  const supported = new Map(
    ASSISTANT_COMMANDS
      .filter((item) => !availableCommands || availableCommands.includes(item.command))
      .map((item) => [item.command.toLowerCase(), item.command]),
  );
  const commands: string[] = [];
  const seen = new Set<string>();
  const text = value.replace(
    /(^|\s)(\/[a-z][\w-]*)(?=\s|$)/gi,
    (match, prefix: string, token: string) => {
      const command = supported.get(token.toLowerCase());
      if (!command) return match;
      if (!seen.has(command)) {
        seen.add(command);
        commands.push(command);
      }
      return prefix;
    },
  ).replace(/^[ \t]+/, "").replace(/[ \t]{2,}/g, " ");

  return { commands, text };
}

export function serializeAssistantCommandInput(
  commands: readonly string[],
  text: string,
): string {
  const prefix = commands.join(" ");
  if (!prefix) return text;
  return text ? `${prefix} ${text}` : `${prefix} `;
}
