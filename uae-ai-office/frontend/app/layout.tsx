import type { ReactNode } from "react";
import { AuthProvider } from "@/lib/auth-context";
import { LocaleProvider } from "@/lib/i18n";
import { ThemeProvider, THEME_BOOTSTRAP_SCRIPT } from "@/lib/theme-context";
import "./globals.css";

export const metadata = {
  title: "UAE AI Office",
  description: "AI-powered business office for UAE contracting and maintenance companies.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  // lang/dir start at the English default here and are kept in sync with
  // the active locale by LocaleProvider (see lib/i18n/LocaleContext.tsx)
  // once the stored preference (if any) is read on mount. data-theme is
  // stamped by the bootstrap script below before first paint -- which is
  // exactly the attribute mismatch React would otherwise warn about on
  // hydration, so <html> opts out of that check.
  return (
    <html lang="en" dir="ltr" data-theme="dark" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        {/* App Router: this <link> lives in the ROOT layout, so it is emitted
            for every route -- the pages/_document caveat the rule warns about
            does not apply here. */}
        {/* eslint-disable-next-line @next/next/no-page-custom-font */}
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=Sora:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap"
        />
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOTSTRAP_SCRIPT }} />
      </head>
      <body>
        <ThemeProvider>
          <LocaleProvider>
            <AuthProvider>{children}</AuthProvider>
          </LocaleProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
