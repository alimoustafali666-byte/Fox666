import type { Locale } from "./types";

// UAE-specific regional formatting for both languages, matching the
// company.country="AE" already shown in the app shell -- not just
// "some English" vs "some Arabic".
const INTL_LOCALES: Record<Locale, string> = { en: "en-AE", ar: "ar-AE" };

export function formatDate(
  locale: Locale,
  value: string | Date,
  options?: Intl.DateTimeFormatOptions
): string {
  const date = typeof value === "string" ? new Date(value) : value;
  return date.toLocaleDateString(INTL_LOCALES[locale], options);
}

export function formatDateTime(
  locale: Locale,
  value: string | Date,
  options?: Intl.DateTimeFormatOptions
): string {
  const date = typeof value === "string" ? new Date(value) : value;
  return date.toLocaleString(INTL_LOCALES[locale], options);
}

