import type { ReactNode } from "react";
import { CollaborationProvider } from "@/components/collaboration/CollaborationContext";
import { ConversationList } from "@/components/collaboration/ConversationList";
import styles from "./MessagesLayout.module.css";

export default function MessagesLayout({ children }: { children: ReactNode }) {
  return (
    <CollaborationProvider>
      <div className={styles.wrap}>
        <ConversationList />
        <div className={styles.main}>{children}</div>
      </div>
    </CollaborationProvider>
  );
}

