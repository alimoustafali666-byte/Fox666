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
      <body>
        <LocaleProvider>
          <AuthProvider>{children}</AuthProvider>
        </LocaleProvider>
      </body>
    </html>
  );
}

