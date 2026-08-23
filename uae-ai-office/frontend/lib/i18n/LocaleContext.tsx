"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { DEFAULT_LOCALE, type Locale, type Translations, type TranslationKey } from "./types";
import en from "./translations/en";
import ar from "./translations/ar";

const DICTIONARIES: Record<Locale, Translations> = { en, ar };
const DIRECTIONS: Record<Locale, "ltr" | "rtl"> = { en: "ltr", ar: "rtl" };
const STORAGE_KEY = "uae-ai-office.locale";

function isLocale(value: string | null): value is Locale {
  return value === "en" || value === "ar";
}

function readStoredLocale(): Locale | null {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    return isLocale(stored) ? stored : null;
  } catch {
    // Private browsing / storage blocked -- fall back to the default
    // rather than breaking the page over a non-essential preference.
    return null;
  }
}

function lookup(dict: Translations, key: TranslationKey): string {
  const value = key.split(".").reduce<unknown>((node, part) => {
    if (node && typeof node === "object" && part in node) {
      return (node as Record<string, unknown>)[part];
    }
    return undefined;
  }, dict);
  return typeof value === "string" ? value : key;
}

// {name}-style interpolation only -- no HTML is ever parsed out of a
// translation string or a param, so there is no injection surface here:
// the result is always rendered as plain React text content (which
// React escapes), never through dangerouslySetInnerHTML.
function interpolate(template: string, params?: Record<string, string | number>): string {
  if (!params) return template;
  return template.replace(/\{(\w+)\}/g, (match, token: string) =>
    token in params ? String(params[token]) : match
  );
}

interface LocaleContextValue {
  locale: Locale;
  dir: "ltr" | "rtl";
  setLocale: (locale: Locale) => void;
  t: (key: TranslationKey, params?: Record<string, string | number>) => string;
}

const LocaleContext = createContext<LocaleContextValue | null>(null);

export function LocaleProvider({ children }: { children: ReactNode }) {
  // Always starts at the default on both server and first client render
  // (no layout flash from a mismatched SSR guess) -- the stored
  // preference, if any, is applied a moment later in the effect below.
  const [locale, setLocaleState] = useState<Locale>(DEFAULT_LOCALE);

  useEffect(() => {
    const stored = readStoredLocale();
    if (stored) setLocaleState(stored);
  }, []);

  useEffect(() => {
    document.documentElement.lang = locale;
    document.documentElement.dir = DIRECTIONS[locale];
  }, [locale]);

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // Non-essential: the preference just won't survive a refresh.
    }
  }, []);

  const t = useCallback(
    (key: TranslationKey, params?: Record<string, string | number>) =>
      interpolate(lookup(DICTIONARIES[locale], key), params),
    [locale]
  );

  const value = useMemo<LocaleContextValue>(
    () => ({ locale, dir: DIRECTIONS[locale], setLocale, t }),
    [locale, setLocale, t]
  );

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

export function useTranslation(): LocaleContextValue {
  const ctx = useContext(LocaleContext);
  if (!ctx) throw new Error("useTranslation must be used within LocaleProvider");
  return ctx;
}

