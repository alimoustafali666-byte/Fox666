import type { ReactNode } from "react";
import { AskConversationsProvider } from "@/components/ask/AskConversationsContext";
import { ConversationSidebar } from "@/components/ask/ConversationSidebar";
import styles from "./AskLayout.module.css";

export default function AskLayout({ children }: { children: ReactNode }) {
  return (
    <AskConversationsProvider>
      <div className={styles.wrap}>
        <ConversationSidebar />
        <div className={styles.main}>{children}</div>
      </div>
    </AskConversationsProvider>
  );
}

