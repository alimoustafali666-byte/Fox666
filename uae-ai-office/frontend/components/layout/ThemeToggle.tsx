"use client";

import { useTranslation } from "@/lib/i18n";
import { useTheme } from "@/lib/theme-context";
import { MoonIcon, SunIcon } from "./icons";
import styles from "./ThemeToggle.module.css";

/** Sun / switch / current-mode pill, as in the approved master design. */
export function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();
  const { t } = useTranslation();
  const dark = theme === "dark";

  return (
    <button
      type="button"
      className={styles.toggle}
      onClick={toggleTheme}
      role="switch"
      aria-checked={dark}
      aria-label={t("header.theme")}
      title={dark ? t("header.themeLight") : t("header.themeDark")}
    >
      <SunIcon width={14} height={14} className={styles.sun} />
      <span className={styles.track} aria-hidden="true">
        <span className={styles.knob} />
      </span>
      <span className={styles.badge}>
        {/* The badge names the theme that is active, so its icon has to follow
            the label -- a moon beside the word "Light" reads as a bug. */}
        {dark ? <MoonIcon width={12} height={12} /> : <SunIcon width={12} height={12} />}
        {dark ? t("header.themeDark") : t("header.themeLight")}
      </span>
    </button>
  );
}
