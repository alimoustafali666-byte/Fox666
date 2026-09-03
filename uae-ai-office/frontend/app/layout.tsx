import type { ReactNode } from "react";
import { AuthProvider } from "@/lib/auth-context";
import { LocaleProvider } from "@/lib/i18n";
import "./globals.css";

export const metadata = {
  title: "UAE AI Office",
  description: "AI-powered business office for UAE contracting and maintenance companies.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  // lang/dir start at the English default here and are kept in sync with
  // the active locale by LocaleProvider (see lib/i18n/LocaleContext.tsx)
  // once the stored preference (if any) is read on mount.
  return (
    <html lang="en" dir="ltr">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=Sora:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap"
        />
      </head>
      <body>
        <LocaleProvider>
          <AuthProvider>{children}</AuthProvider>
        </LocaleProvider>
      </body>
    </html>
  );
}

