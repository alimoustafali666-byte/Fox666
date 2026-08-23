"use client";

import { useEffect, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useTranslation } from "@/lib/i18n";
import { BrandMark } from "@/components/layout/BrandMark";
import clsx from "@/components/ui/clsx";
import styles from "./AuthLayout.module.css";

function CheckIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
      <path d="M2.2 6.2 4.6 8.6 9.8 3.4" stroke="#eafcff" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export default function AuthLayout({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  const router = useRouter();
  const { t } = useTranslation();

  useEffect(() => {
    if (status === "authenticated") {
      router.replace("/dashboard");
    }
  }, [status, router]);

  return (
    <div className={styles.wrap}>
      <div className={styles.hero}>
        <div className={clsx(styles.heroTexture, "uae-dot-grid")} aria-hidden="true" />
        <div className={styles.heroGlow} aria-hidden="true" />
        <div className={styles.heroGlowViolet} aria-hidden="true" />
        <div className={styles.heroContent}>
          <div className={styles.brand}>
            <BrandMark size={40} />
            <span className={styles.brandName}>{t("common.appName")}</span>
          </div>
          <div className={styles.heroEyebrow}>{t("auth.hero.eyebrow")}</div>
          <h1 className={styles.heroTitle}>{t("auth.hero.title")}</h1>
          <p className={styles.heroSubtitle}>{t("auth.hero.subtitle")}</p>
          <ul className={styles.heroList}>
            <li>
              <CheckIcon />
              {t("auth.hero.bullet1")}
            </li>
            <li>
              <CheckIcon />
              {t("auth.hero.bullet2")}
            </li>
            <li>
              <CheckIcon />
              {t("auth.hero.bullet3")}
            </li>
          </ul>
        </div>
      </div>

      <div className={styles.formSide}>
        <div className={styles.brandCompact}>
          <BrandMark size={30} />
          <span className={styles.brandName}>{t("common.appName")}</span>
        </div>
        <div className={clsx(styles.panel, "uae-fade-in")}>{children}</div>
      </div>
    </div>
  );
}

