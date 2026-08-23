"use client";

import { useEffect, useState, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useTranslation } from "@/lib/i18n";
import { LoadingBlock } from "../ui/Spinner";
import { Header } from "./Header";
import { Sidebar } from "./Sidebar";
import styles from "./AppShell.module.css";

export function AppShell({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const { t } = useTranslation();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  useEffect(() => {
    if (status === "unauthenticated") {
      router.replace("/login");
    }
  }, [status, router]);

  // Closes the mobile drawer automatically on navigation, so a link tap
  // doesn't leave the overlay open behind the new page.
  useEffect(() => {
    setMobileNavOpen(false);
  }, [pathname]);

  if (status !== "authenticated") {
    return (
      <div className={styles.guardLoading}>
        <LoadingBlock label={t("appShell.loadingWorkspace")} />
      </div>
    );
  }

  return (
    <>
      <Sidebar open={mobileNavOpen} onClose={() => setMobileNavOpen(false)} />
      <div className={styles.main}>
        <Header onToggleMenu={() => setMobileNavOpen((v) => !v)} />
        <main className={styles.content}>{children}</main>
      </div>
    </>
  );
}

