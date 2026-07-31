import { useMemo, useState } from "react";
import { Banknote, BellRing, Check, CreditCard, Languages, Monitor, Moon, Palette, Search, SlidersHorizontal, Sun, UserRound } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";

import NotificationSettingsSection from "@/components/NotificationSettingsSection";
import AccountSettingsSection from "@/components/AccountSettingsSection";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useI18n } from "@/i18n/i18n-context";
import type { LanguageMode } from "@/i18n/i18n-storage";
import { cn } from "@/lib/utils";
import { useTheme } from "@/theme/theme-context";
import type { ThemeMode } from "@/theme/theme-storage";
import type { JournalCurrencyCode } from "@/api/client";
import { JOURNAL_CURRENCY_OPTIONS } from "@/journal/journal-currency";
import { useJournalSettings } from "@/journal/journal-settings-context";
import { settingsControlStyles } from "./settings-ui-config";
import BillingSettingsSection from "@/billing/BillingSettingsSection";

type SettingsSection = "general" | "account" | "billing" | "appearance" | "notifications";

const sections: Array<{
  id: SettingsSection;
  icon: typeof SlidersHorizontal;
  labelKey: string;
}> = [
  { id: "general", icon: SlidersHorizontal, labelKey: "settings.page.general" },
  { id: "account", icon: UserRound, labelKey: "settings.page.account" },
  { id: "billing", icon: CreditCard, labelKey: "settings.page.billing" },
  { id: "appearance", icon: Palette, labelKey: "settings.menu.appearance" },
  { id: "notifications", icon: BellRing, labelKey: "settings.menu.notifications" },
];

export default function SettingsPage() {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const [query, setQuery] = useState("");
  const { themeMode, setThemeMode } = useTheme();
  const { languageMode, setLanguageMode } = useI18n();
  const { currencyCode, loaded: journalSettingsLoaded, setCurrencyCode } = useJournalSettings();
  const requestedSection = searchParams.get("section");
  const activeSection: SettingsSection = sections.some((item) => item.id === requestedSection)
    ? requestedSection as SettingsSection
    : "general";

  const visibleSections = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase();
    if (!normalized) return sections;
    return sections.filter((section) => t(section.labelKey).toLocaleLowerCase().includes(normalized));
  }, [query, t]);

  const openSection = (section: SettingsSection) => {
    setSearchParams(section === "general" ? {} : { section });
  };

  return (
    <div className="-mx-[10px] -mb-[10px] -mt-2 grid min-h-[calc(100vh-10px)] grid-cols-[220px_minmax(0,1fr)] overflow-hidden md:-mt-2 max-md:min-h-0 max-md:grid-cols-1 max-md:overflow-visible">
      <aside className="border-r border-border bg-muted/25 px-3 py-6 max-md:border-b max-md:border-r-0 max-md:py-3">
        <div className="px-2 text-subheading font-semibold text-foreground">{t("settings.page.title")}</div>
        <div className="relative mt-4">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-[var(--icon-sm)] -translate-y-1/2 text-muted-foreground" />
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={t("settings.page.search")}
            className="pl-9"
            style={settingsControlStyles.inputStyle}
          />
        </div>

        <div className="mb-2 mt-6 px-2 text-caption font-medium text-muted-foreground max-md:hidden">
          {t("settings.page.personal")}
        </div>
        <nav className="flex flex-col gap-1 max-md:mt-3 max-md:flex-row max-md:overflow-x-auto">
          {visibleSections.map((section) => {
            const Icon = section.icon;
            return (
              <button
                key={section.id}
                type="button"
                onClick={() => openSection(section.id)}
                className={cn(
                  "flex h-9 items-center gap-2 rounded-[9px] px-3 text-left text-ui text-muted-foreground transition-colors hover:bg-muted hover:text-foreground max-md:shrink-0",
                  activeSection === section.id && "bg-muted text-foreground",
                )}
                style={settingsControlStyles.buttonStyle}
              >
                <Icon className="size-[var(--icon-sm)]" />
                {t(section.labelKey)}
              </button>
            );
          })}
          {!visibleSections.length ? (
            <div className="px-3 py-2 text-caption text-muted-foreground">{t("settings.page.noResults")}</div>
          ) : null}
        </nav>
      </aside>

      <main className="min-w-0 overflow-y-auto bg-background px-6 py-10 sm:px-10 lg:px-16">
        <div className="mx-auto max-w-[960px]">
          {activeSection === "general" ? (
            <SettingsContentHeader
              title={t("settings.page.general")}
            >
              <SettingsGroup title={t("settings.page.languageRegion")}>
                <SettingsRow
                  icon={<Languages />}
                  title={t("settings.page.language")}
                  description={t("settings.page.languageDescription")}
                  control={(
                    <Select value={languageMode} onValueChange={(value) => setLanguageMode(value as LanguageMode)}>
                      <SelectTrigger size="sm" className="min-w-[150px]" style={settingsControlStyles.inputStyle}>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="system">{t("settings.language.system")}</SelectItem>
                        <SelectItem value="zh">{t("settings.language.zh")}</SelectItem>
                        <SelectItem value="en">{t("settings.language.en")}</SelectItem>
                      </SelectContent>
                    </Select>
                  )}
                />
              </SettingsGroup>
              <SettingsGroup title={t("settings.page.tradingJournal")}>
                <SettingsRow
                  icon={<Banknote />}
                  title={t("settings.page.journalCurrency")}
                  description={t("settings.page.journalCurrencyDescription")}
                  control={(
                    <Select
                      value={currencyCode ?? undefined}
                      disabled={!journalSettingsLoaded}
                      onValueChange={(value) => {
                        setCurrencyCode(value as JournalCurrencyCode).catch(() => {});
                      }}
                    >
                      <SelectTrigger
                        size="sm"
                        className="min-w-[190px]"
                        style={settingsControlStyles.inputStyle}
                      >
                        <SelectValue placeholder={t("settings.page.journalCurrencyPlaceholder")} />
                      </SelectTrigger>
                      <SelectContent>
                        {JOURNAL_CURRENCY_OPTIONS.map((option) => (
                          <SelectItem key={option.code} value={option.code}>
                            {option.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                />
              </SettingsGroup>
            </SettingsContentHeader>
          ) : null}

          {activeSection === "appearance" ? (
            <SettingsContentHeader
              title={t("settings.menu.appearance")}
            >
              <SettingsGroup title={t("settings.themeMode")}>
                <div className="grid grid-cols-1 gap-3 p-5 sm:grid-cols-3">
                  {([
                    { value: "system" as const, icon: Monitor, label: t("settings.theme.system") },
                    { value: "light" as const, icon: Sun, label: t("settings.theme.light") },
                    { value: "dark" as const, icon: Moon, label: t("settings.theme.dark") },
                  ]).map((option) => {
                    const Icon = option.icon;
                    const selected = themeMode === option.value;
                    return (
                      <Button
                        key={option.value}
                        variant="outline"
                        size="sm"
                        style={settingsControlStyles.buttonStyle}
                        className={cn(
                          "h-auto justify-start px-4 py-4",
                          selected && "border-primary bg-[var(--accent-soft)] ring-1 ring-[var(--accent-strong)] hover:bg-[var(--accent-soft)]",
                        )}
                        onClick={() => setThemeMode(option.value as ThemeMode)}
                        aria-pressed={selected}
                      >
                        <Icon className="size-[var(--icon-sm)]" />
                        {option.label}
                        {selected ? <Check className="ml-auto size-[var(--icon-sm)] text-primary" /> : null}
                      </Button>
                    );
                  })}
                </div>
              </SettingsGroup>
            </SettingsContentHeader>
          ) : null}

          {activeSection === "account" ? (
            <SettingsContentHeader title={t("settings.page.account")}>
              <AccountSettingsSection />
            </SettingsContentHeader>
          ) : null}

          {activeSection === "billing" ? (
            <SettingsContentHeader title={t("settings.page.billing")}>
              <BillingSettingsSection />
            </SettingsContentHeader>
          ) : null}

          {activeSection === "notifications" ? (
            <SettingsContentHeader
              title={t("notifications.title")}
            >
              <NotificationSettingsSection />
            </SettingsContentHeader>
          ) : null}
        </div>
      </main>
    </div>
  );
}

function SettingsContentHeader({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <h1 className="text-heading font-semibold text-foreground">{title}</h1>
      <div className="mt-9 flex flex-col gap-8">{children}</div>
    </div>
  );
}

function SettingsGroup({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h2 className="mb-3 text-ui font-semibold text-foreground">{title}</h2>
      <div className="overflow-hidden rounded-[12px] border border-border bg-[var(--panel-card-bg)]">
        {children}
      </div>
    </section>
  );
}

function SettingsRow({
  icon,
  title,
  description,
  control,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
  control: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-4 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex min-w-0 items-start gap-3">
        <span className="mt-0.5 text-muted-foreground [&_svg]:size-[var(--icon-sm)]">{icon}</span>
        <div className="title-description-stack">
          <div className="text-ui font-medium text-foreground">{title}</div>
          <div className="text-caption text-muted-foreground">{description}</div>
        </div>
      </div>
      <div className="shrink-0 pl-7 sm:pl-0">{control}</div>
    </div>
  );
}
