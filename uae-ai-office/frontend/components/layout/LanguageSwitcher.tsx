"use client";

import { useTranslation } from "@/lib/i18n";
import type { Locale } from "@/lib/i18n";
import clsx from "../ui/clsx";
import styles from "./LanguageSwitcher.module.css";

// Each option is always rendered in its OWN language's script ("EN" /
// "العربية"), regardless of which locale is currently active -- these
// are language names, not translated UI copy, the same convention most
// bilingual products use for a language picker.
const OPTIONS: { locale: Locale; label: string }[] = [
  { locale: "en", label: "EN" },
  { locale: "ar", label: "العربية" },
];

export function LanguageSwitcher() {
  const { locale, setLocale, t } = useTranslation();

  return (
    <div className={styles.switcher} role="group" aria-label={t("common.language")}>
      {OPTIONS.map((option) => (
        <button
          key={option.locale}
          type="button"
          className={clsx(styles.option, locale === option.locale && styles.optionActive)}
          aria-pressed={locale === option.locale}
          onClick={() => setLocale(option.locale)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

