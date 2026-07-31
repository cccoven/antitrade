import type { JournalCurrencyCode } from "@/api/client";

export const JOURNAL_CURRENCY_OPTIONS: Array<{
  code: JournalCurrencyCode;
  label: string;
}> = [
  { code: "CNY", label: "CNY · ¥" },
  { code: "USD", label: "USD · $" },
  { code: "HKD", label: "HKD · HK$" },
  { code: "EUR", label: "EUR · €" },
  { code: "GBP", label: "GBP · £" },
  { code: "JPY", label: "JPY · ¥" },
  { code: "USDT", label: "USDT · Tether" },
];

interface FormatJournalMoneyOptions {
  signed?: boolean;
}

export const JOURNAL_AMOUNT_MASK = "••••";

export function maskJournalMoney(
  value: number | null | undefined,
  formattedValue: string,
  amountsVisible: boolean,
): string {
  if (value == null || amountsVisible) return formattedValue;
  return JOURNAL_AMOUNT_MASK;
}

export function formatJournalMoney(
  value: number | null | undefined,
  currencyCode: JournalCurrencyCode | null,
  locale: string,
  options: FormatJournalMoneyOptions = {},
): string {
  if (value == null) return "—";
  const signDisplay = options.signed ? "exceptZero" : "auto";

  if (currencyCode === "USDT") {
    const number = new Intl.NumberFormat(locale, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
      signDisplay,
    }).format(value);
    return `${number} USDT`;
  }

  if (currencyCode) {
    return new Intl.NumberFormat(locale, {
      style: "currency",
      currency: currencyCode,
      currencyDisplay: "narrowSymbol",
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
      signDisplay,
    }).format(value);
  }

  return new Intl.NumberFormat(locale, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
    signDisplay,
  }).format(value);
}
