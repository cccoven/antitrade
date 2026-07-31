import { useTranslation } from "react-i18next";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandItem,
  CommandList,
  CommandShortcut,
} from "@/components/ui/command";
import { cn } from "@/lib/utils";
import type { AssistantCommandGroup, ResolvedAssistantCommand } from "./command-registry";

const GROUP_ORDER: AssistantCommandGroup[] = ["market", "personal", "assistant"];

interface SlashCommandMenuProps {
  commands: ResolvedAssistantCommand[];
  selectedIndex: number;
  onSelect: (command: ResolvedAssistantCommand) => void;
}

export function SlashCommandMenu({ commands, selectedIndex, onSelect }: SlashCommandMenuProps) {
  const { t } = useTranslation();

  return (
    <Command
      shouldFilter={false}
      value={commands[selectedIndex]?.command ?? ""}
      className="rounded-[12px] border border-border bg-popover shadow-[var(--shadow-md)]"
      onMouseDown={(event) => event.preventDefault()}
    >
      <CommandList className="max-h-[320px] p-1">
        <CommandEmpty>{t("assistant.command.empty")}</CommandEmpty>
        {GROUP_ORDER.map((group) => {
          const groupCommands = commands.filter((item) => item.group === group);
          if (groupCommands.length === 0) return null;
          return (
            <CommandGroup
              key={group}
              heading={groupCommands[0].groupLabel}
              className="py-0.5 [&_[cmdk-group-heading]]:text-caption [&_[cmdk-group-heading]]:font-medium [&_[cmdk-group-heading]]:leading-4"
            >
              {groupCommands.map((item) => {
                const itemIndex = commands.indexOf(item);
                const Icon = item.icon;
                return (
                  <CommandItem
                    key={item.command}
                    value={item.command}
                    className={cn(
                      "items-start py-1.5",
                      itemIndex === selectedIndex && "bg-accent text-accent-foreground",
                    )}
                    onSelect={() => onSelect(item)}
                  >
                    <Icon className="mt-0.5 size-[var(--icon-xs)]" />
                    <span className="min-w-0 flex-1">
                      <span className="flex items-center gap-1.5 leading-4">
                        <span className="text-ui font-semibold">{item.command}</span>
                        <span className="truncate text-caption font-normal text-muted-foreground">{item.label}</span>
                      </span>
                      <span className="mt-0.5 block truncate text-micro leading-4 text-[var(--text-faint)]">
                        {item.description}
                      </span>
                    </span>
                    <CommandShortcut className="text-micro">↵</CommandShortcut>
                  </CommandItem>
                );
              })}
            </CommandGroup>
          );
        })}
      </CommandList>
    </Command>
  );
}
